/**
 * Session Manager Library for Claude Code
 * Provides core session CRUD operations for listing, loading, and managing sessions
 *
 * Sessions are stored as markdown files in ~/.claude/sessions/ with format:
 * - YYYY-MM-DD-session.tmp (old format)
 * - YYYY-MM-DD-<short-id>-session.tmp (new format)
 */

const fs = require('fs');
const path = require('path');

const {
  getSessionsDir,
  readFile,
  log
} = require('./utils');

// Session filename pattern: YYYY-MM-DD-[short-id]-session.tmp
// The short-id is optional (old format) and can be 8+ alphanumeric characters
// Matches: "2026-02-01-session.tmp" or "2026-02-01-a1b2c3d4-session.tmp"
const SESSION_FILENAME_REGEX = /^(\d{4}-\d{2}-\d{2})(?:-([a-z0-9]{8,}))?-session\.tmp$/;

/**
 * Parse session filename to extract metadata
 * @param {string} filename - Session filename (e.g., "2026-01-17-abc123-session.tmp" or "2026-01-17-session.tmp")
 * @returns {object|null} Parsed metadata or null if invalid
 */
function parseSessionFilename(filename) {
  const match = filename.match(SESSION_FILENAME_REGEX);
  if (!match) return null;

  const dateStr = match[1];

  // Validate date components are calendar-accurate (not just format)
  const [year, month, day] = dateStr.split('-').map(Number);
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  // Reject impossible dates like Feb 31, Apr 31 — Date constructor rolls
  // over invalid days (e.g., Feb 31 → Mar 3), so check month roundtrips
  const d = new Date(year, month - 1, day);
  if (d.getMonth() !== month - 1 || d.getDate() !== day) return null;

  // match[2] is undefined for old format (no ID)
  const shortId = match[2] || 'no-id';

  return {
    filename,
    shortId,
    date: dateStr,
    // Use local-time constructor (consistent with validation on line 40)
    // new Date(dateStr) interprets YYYY-MM-DD as UTC midnight which shows
    // as the previous day in negative UTC offset timezones
    datetime: new Date(year, month - 1, day)
  };
}

/**
 * Get the full path to a session file
 * @param {string} filename - Session filename
 * @returns {string} Full path to session file
 */
function getSessionPath(filename) {
  return path.join(getSessionsDir(), filename);
}

/**
 * Read and parse session markdown content
 * @param {string} sessionPath - Full path to session file
 * @returns {string|null} Session content or null if not found
 */
function getSessionContent(sessionPath) {
  return readFile(sessionPath);
}

/**
 * Extract a checklist section from markdown content.
 * @param {string} content - Full document content
 * @param {RegExp} sectionRe - Regex to capture the section body
 * @param {RegExp} itemRe - Regex to match individual items
 * @param {RegExp} cleanRe - Regex to strip the item prefix
 */
function _extractChecklistItems(content, sectionRe, itemRe, cleanRe) {
  const section = content.match(sectionRe);
  if (!section) return [];
  const items = section[1].match(itemRe);
  if (!items) return [];
  return items.map(item => item.replace(cleanRe, '').trim());
}

/**
 * Parse session metadata from markdown content
 * @param {string} content - Session markdown content
 * @returns {object} Parsed metadata
 */
function parseSessionMetadata(content) {
  const metadata = {
    title: null, date: null, started: null, lastUpdated: null,
    completed: [], inProgress: [], notes: '', context: ''
  };

  if (!content) return metadata;

  const m = (re) => { const r = content.match(re); return r ? r[1].trim() : null; };

  metadata.title       = m(/^#\s+(.+)$/m);
  metadata.date        = m(/\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})/);
  metadata.started     = m(/\*\*Started:\*\*\s*([\d:]+)/);
  metadata.lastUpdated = m(/\*\*Last Updated:\*\*\s*([\d:]+)/);
  metadata.notes       = m(/### Notes for Next Session\s*\n([\s\S]*?)(?=###|\n\n|$)/) || '';
  metadata.context     = m(/### Context to Load\s*\n```\n([\s\S]*?)```/) || '';

  metadata.completed  = _extractChecklistItems(
    content,
    /### Completed\s*\n([\s\S]*?)(?=###|\n\n|$)/,
    /- \[x\]\s*(.+)/g,
    /- \[x\]\s*/
  );
  metadata.inProgress = _extractChecklistItems(
    content,
    /### In Progress\s*\n([\s\S]*?)(?=###|\n\n|$)/,
    /- \[ \]\s*(.+)/g,
    /- \[ \]\s*/
  );

  return metadata;
}

/**
 * Calculate statistics for a session
 * @param {string} sessionPathOrContent - Full path to session file, OR
 *   the pre-read content string (to avoid redundant disk reads when
 *   the caller already has the content loaded).
 * @returns {object} Statistics object
 */
function getSessionStats(sessionPathOrContent) {
  // Accept pre-read content string to avoid redundant file reads.
  // If the argument looks like a file path (no newlines, ends with .tmp,
  // starts with / on Unix or drive letter on Windows), read from disk.
  // Otherwise treat it as content.
  const looksLikePath = typeof sessionPathOrContent === 'string' &&
    !sessionPathOrContent.includes('\n') &&
    sessionPathOrContent.endsWith('.tmp') &&
    (sessionPathOrContent.startsWith('/') || /^[A-Za-z]:[/\\]/.test(sessionPathOrContent));
  const content = looksLikePath
    ? getSessionContent(sessionPathOrContent)
    : sessionPathOrContent;

  const metadata = parseSessionMetadata(content);

  return {
    totalItems: metadata.completed.length + metadata.inProgress.length,
    completedItems: metadata.completed.length,
    inProgressItems: metadata.inProgress.length,
    lineCount: content ? content.split('\n').length : 0,
    hasNotes: !!metadata.notes,
    hasContext: !!metadata.context
  };
}

/**
 * Convert a directory entry to a session object, applying filters.
 * Returns null if the entry should be excluded.
 */
function _entryToSession(entry, sessionsDir, dateFilter, searchFilter) {
  if (!entry.isFile() || !entry.name.endsWith('.tmp')) return null;
  const metadata = parseSessionFilename(entry.name);
  if (!metadata) return null;
  if (dateFilter && metadata.date !== dateFilter) return null;
  if (searchFilter && !metadata.shortId.includes(searchFilter)) return null;
  const sessionPath = path.join(sessionsDir, entry.name);
  try {
    const stats = fs.statSync(sessionPath);
    return {
      ...metadata,
      sessionPath,
      hasContent: stats.size > 0,
      size: stats.size,
      modifiedTime: stats.mtime,
      createdTime: stats.birthtime || stats.ctime
    };
  } catch {
    return null; // File deleted between readdir and stat
  }
}

/**
 * Get all sessions with optional filtering and pagination
 * @param {object} options - Options object
 * @param {number} options.limit - Maximum number of sessions to return
 * @param {number} options.offset - Number of sessions to skip
 * @param {string} options.date - Filter by date (YYYY-MM-DD format)
 * @param {string} options.search - Search in short ID
 * @returns {object} Object with sessions array and pagination info
 */
function getAllSessions(options = {}) {
  const { limit: rawLimit = 50, offset: rawOffset = 0, date = null, search = null } = options;

  // Clamp to safe non-negative integers (0 is falsy, so use Number.isNaN not ||)
  const offsetNum = Number(rawOffset);
  const offset = Number.isNaN(offsetNum) ? 0 : Math.max(0, Math.floor(offsetNum));
  const limitNum = Number(rawLimit);
  const limit = Number.isNaN(limitNum) ? 50 : Math.max(1, Math.floor(limitNum));

  const sessionsDir = getSessionsDir();
  if (!fs.existsSync(sessionsDir)) {
    return { sessions: [], total: 0, offset, limit, hasMore: false };
  }

  const entries = fs.readdirSync(sessionsDir, { withFileTypes: true });
  const sessions = entries
    .map(entry => _entryToSession(entry, sessionsDir, date, search))
    .filter(Boolean)
    .sort((a, b) => b.modifiedTime - a.modifiedTime);

  return {
    sessions: sessions.slice(offset, offset + limit),
    total: sessions.length,
    offset,
    limit,
    hasMore: offset + limit < sessions.length
  };
}

/** Check if a session filename/metadata matches the requested ID. */
function _matchesSessionId(metadata, filename, sessionId) {
  const shortIdMatch = sessionId.length > 0 && metadata.shortId !== 'no-id' && metadata.shortId.startsWith(sessionId);
  const filenameMatch = filename === sessionId || filename === `${sessionId}.tmp`;
  const noIdMatch = metadata.shortId === 'no-id' && filename === `${sessionId}-session.tmp`;
  return shortIdMatch || filenameMatch || noIdMatch;
}

/**
 * Get a single session by ID (short ID or full path)
 * @param {string} sessionId - Short ID or session filename
 * @param {boolean} includeContent - Include session content
 * @returns {object|null} Session object or null if not found
 */
function getSessionById(sessionId, includeContent = false) {
  const sessionsDir = getSessionsDir();
  if (!fs.existsSync(sessionsDir)) return null;

  const entries = fs.readdirSync(sessionsDir, { withFileTypes: true });

  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith('.tmp')) continue;
    const filename = entry.name;
    const metadata = parseSessionFilename(filename);
    if (!metadata || !_matchesSessionId(metadata, filename, sessionId)) continue;

    const sessionPath = path.join(sessionsDir, filename);
    let stats;
    try { stats = fs.statSync(sessionPath); } catch { return null; }

    const session = {
      ...metadata, sessionPath,
      size: stats.size, modifiedTime: stats.mtime,
      createdTime: stats.birthtime || stats.ctime
    };

    if (includeContent) {
      session.content  = getSessionContent(sessionPath);
      session.metadata = parseSessionMetadata(session.content);
      session.stats    = getSessionStats(session.content || '');
    }

    return session;
  }

  return null;
}

/**
 * Get session title from content
 * @param {string} sessionPath - Full path to session file
 * @returns {string} Title or default text
 */
function getSessionTitle(sessionPath) {
  const content = getSessionContent(sessionPath);
  const metadata = parseSessionMetadata(content);

  return metadata.title || 'Untitled Session';
}

/**
 * Format session size in human-readable format
 * @param {string} sessionPath - Full path to session file
 * @returns {string} Formatted size (e.g., "1.2 KB")
 */
function getSessionSize(sessionPath) {
  let stats;
  try {
    stats = fs.statSync(sessionPath);
  } catch {
    return '0 B';
  }
  const size = stats.size;

  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Write session content to file
 * @param {string} sessionPath - Full path to session file
 * @param {string} content - Markdown content to write
 * @returns {boolean} Success status
 */
function writeSessionContent(sessionPath, content) {
  try {
    fs.writeFileSync(sessionPath, content, 'utf8');
    return true;
  } catch (err) {
    log(`[SessionManager] Error writing session: ${err.message}`);
    return false;
  }
}

/**
 * Append content to a session
 * @param {string} sessionPath - Full path to session file
 * @param {string} content - Content to append
 * @returns {boolean} Success status
 */
function appendSessionContent(sessionPath, content) {
  try {
    fs.appendFileSync(sessionPath, content, 'utf8');
    return true;
  } catch (err) {
    log(`[SessionManager] Error appending to session: ${err.message}`);
    return false;
  }
}

/**
 * Delete a session file
 * @param {string} sessionPath - Full path to session file
 * @returns {boolean} Success status
 */
function deleteSession(sessionPath) {
  try {
    if (fs.existsSync(sessionPath)) {
      fs.unlinkSync(sessionPath);
      return true;
    }
    return false;
  } catch (err) {
    log(`[SessionManager] Error deleting session: ${err.message}`);
    return false;
  }
}

/**
 * Check if a session exists
 * @param {string} sessionPath - Full path to session file
 * @returns {boolean} True if session exists
 */
function sessionExists(sessionPath) {
  try {
    return fs.statSync(sessionPath).isFile();
  } catch {
    return false;
  }
}

module.exports = {
  parseSessionFilename,
  getSessionPath,
  getSessionContent,
  parseSessionMetadata,
  getSessionStats,
  getSessionTitle,
  getSessionSize,
  getAllSessions,
  getSessionById,
  writeSessionContent,
  appendSessionContent,
  deleteSession,
  sessionExists
};
