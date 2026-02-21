-- =============================================================================
-- PART 7: RLS POLICIES - RAG SCHEMA
-- Run after Part 6
-- =============================================================================

-- -----------------------------------------------------------------------------
-- RAG Documents Policies
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own rag documents" ON rag.documents;
DROP POLICY IF EXISTS "Users can insert own rag documents" ON rag.documents;
DROP POLICY IF EXISTS "Users can update own rag documents" ON rag.documents;
DROP POLICY IF EXISTS "Users can delete own rag documents" ON rag.documents;
DROP POLICY IF EXISTS "Service role full access to rag documents" ON rag.documents;

CREATE POLICY "Users can view own rag documents" ON rag.documents
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own rag documents" ON rag.documents
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own rag documents" ON rag.documents
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own rag documents" ON rag.documents
    FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Service role full access to rag documents" ON rag.documents
    FOR ALL USING (auth.role() = 'service_role');

-- -----------------------------------------------------------------------------
-- RAG Chunks Policies
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own chunks" ON rag.chunks;
DROP POLICY IF EXISTS "Service role full access to rag chunks" ON rag.chunks;

CREATE POLICY "Users can view own chunks" ON rag.chunks
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM rag.documents d 
            WHERE d.id = document_id AND d.user_id = auth.uid()
        )
    );

CREATE POLICY "Service role full access to rag chunks" ON rag.chunks
    FOR ALL USING (auth.role() = 'service_role');

-- -----------------------------------------------------------------------------
-- RAG Collections Policies
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own collections" ON rag.collections;
DROP POLICY IF EXISTS "Users can insert own collections" ON rag.collections;
DROP POLICY IF EXISTS "Users can update own collections" ON rag.collections;
DROP POLICY IF EXISTS "Users can delete own collections" ON rag.collections;
DROP POLICY IF EXISTS "Service role full access to rag collections" ON rag.collections;

CREATE POLICY "Users can view own collections" ON rag.collections
    FOR SELECT USING (auth.uid() = user_id OR is_public = true);

CREATE POLICY "Users can insert own collections" ON rag.collections
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own collections" ON rag.collections
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own collections" ON rag.collections
    FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Service role full access to rag collections" ON rag.collections
    FOR ALL USING (auth.role() = 'service_role');

-- -----------------------------------------------------------------------------
-- RAG Document Collections Policies
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can manage own document_collections" ON rag.document_collections;
DROP POLICY IF EXISTS "Service role full access to rag document_collections" ON rag.document_collections;

CREATE POLICY "Users can manage own document_collections" ON rag.document_collections
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM rag.documents d 
            WHERE d.id = document_id AND d.user_id = auth.uid()
        )
    );

CREATE POLICY "Service role full access to rag document_collections" ON rag.document_collections
    FOR ALL USING (auth.role() = 'service_role');

-- -----------------------------------------------------------------------------
-- RAG Conversations Policies
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own rag conversations" ON rag.conversations;
DROP POLICY IF EXISTS "Users can insert own rag conversations" ON rag.conversations;
DROP POLICY IF EXISTS "Users can update own rag conversations" ON rag.conversations;
DROP POLICY IF EXISTS "Users can delete own rag conversations" ON rag.conversations;
DROP POLICY IF EXISTS "Service role full access to rag conversations" ON rag.conversations;

CREATE POLICY "Users can view own rag conversations" ON rag.conversations
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own rag conversations" ON rag.conversations
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own rag conversations" ON rag.conversations
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own rag conversations" ON rag.conversations
    FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Service role full access to rag conversations" ON rag.conversations
    FOR ALL USING (auth.role() = 'service_role');

-- -----------------------------------------------------------------------------
-- RAG Messages Policies
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own rag messages" ON rag.messages;
DROP POLICY IF EXISTS "Users can insert own rag messages" ON rag.messages;
DROP POLICY IF EXISTS "Service role full access to rag messages" ON rag.messages;

CREATE POLICY "Users can view own rag messages" ON rag.messages
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM rag.conversations c 
            WHERE c.id = conversation_id AND c.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert own rag messages" ON rag.messages
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM rag.conversations c 
            WHERE c.id = conversation_id AND c.user_id = auth.uid()
        )
    );

CREATE POLICY "Service role full access to rag messages" ON rag.messages
    FOR ALL USING (auth.role() = 'service_role');

-- Verify
SELECT schemaname, tablename, policyname 
FROM pg_policies 
WHERE schemaname = 'rag'
ORDER BY tablename, policyname;
