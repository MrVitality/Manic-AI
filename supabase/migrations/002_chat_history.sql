-- =============================================================================
-- Manic AI - Chat History & Utilities (Single User)
-- Run in Supabase Studio SQL Editor: http://100.111.244.124:3001
-- =============================================================================

-- ========================
-- CONVERSATIONS
-- ========================
CREATE TABLE IF NOT EXISTS public.conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT DEFAULT 'New Conversation',
    model TEXT DEFAULT 'llama3.2:3b',
    system_prompt TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON public.conversations(created_at DESC);

-- ========================
-- MESSAGES
-- ========================
CREATE TABLE IF NOT EXISTS public.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    model TEXT,
    tokens_used INTEGER,
    latency_ms INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON public.messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON public.messages(created_at);

-- ========================
-- SAVED PROMPTS
-- ========================
CREATE TABLE IF NOT EXISTS public.prompts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    description TEXT,
    prompt_text TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    is_favorite BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prompts_category ON public.prompts(category);
CREATE INDEX IF NOT EXISTS idx_prompts_is_favorite ON public.prompts(is_favorite);

-- ========================
-- USAGE TRACKING
-- ========================
CREATE TABLE IF NOT EXISTS public.usage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE SET NULL,
    model TEXT NOT NULL,
    endpoint TEXT DEFAULT 'chat',
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON public.usage_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_logs_model ON public.usage_logs(model);

-- ========================
-- AUTO-UPDATE TRIGGERS
-- ========================
CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON public.conversations
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

CREATE TRIGGER update_prompts_updated_at
    BEFORE UPDATE ON public.prompts
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

-- ========================
-- HELPER FUNCTIONS
-- ========================

-- Get conversation with messages
CREATE OR REPLACE FUNCTION get_conversation_with_messages(conv_id UUID)
RETURNS TABLE (
    conversation_id UUID,
    title TEXT,
    model TEXT,
    system_prompt TEXT,
    messages JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.title,
        c.model,
        c.system_prompt,
        COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'id', m.id,
                    'role', m.role,
                    'content', m.content,
                    'created_at', m.created_at
                ) ORDER BY m.created_at
            ) FILTER (WHERE m.id IS NOT NULL),
            '[]'::jsonb
        ) as messages
    FROM public.conversations c
    LEFT JOIN public.messages m ON c.id = m.conversation_id
    WHERE c.id = conv_id
    GROUP BY c.id;
END;
$$ LANGUAGE plpgsql;

-- Get usage stats
CREATE OR REPLACE FUNCTION get_usage_stats(days_back INTEGER DEFAULT 30)
RETURNS TABLE (
    total_conversations BIGINT,
    total_messages BIGINT,
    total_tokens BIGINT,
    avg_latency_ms NUMERIC,
    top_model TEXT,
    date_range TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        (SELECT COUNT(*) FROM public.conversations WHERE created_at > NOW() - (days_back || ' days')::INTERVAL),
        (SELECT COUNT(*) FROM public.messages WHERE created_at > NOW() - (days_back || ' days')::INTERVAL),
        (SELECT COALESCE(SUM(u.total_tokens), 0) FROM public.usage_logs u WHERE created_at > NOW() - (days_back || ' days')::INTERVAL),
        (SELECT ROUND(AVG(latency_ms), 1) FROM public.usage_logs WHERE created_at > NOW() - (days_back || ' days')::INTERVAL),
        (SELECT model FROM public.usage_logs WHERE created_at > NOW() - (days_back || ' days')::INTERVAL GROUP BY model ORDER BY COUNT(*) DESC LIMIT 1),
        ('Last ' || days_back || ' days')::TEXT;
END;
$$ LANGUAGE plpgsql;

-- ========================
-- SAMPLE PROMPTS (Optional)
-- ========================
INSERT INTO public.prompts (name, description, prompt_text, category, is_favorite) VALUES
    ('Code Review', 'Review code for bugs and improvements', 'Review this code for potential bugs, security issues, and suggest improvements. Focus on best practices and readability.', 'coding', true),
    ('Explain Code', 'Explain what code does', 'Explain what this code does step by step. Include the purpose, inputs, outputs, and any important details.', 'coding', true),
    ('Write Tests', 'Generate unit tests', 'Write comprehensive unit tests for this code. Include edge cases and use appropriate assertions.', 'coding', false),
    ('Summarize', 'Summarize text or document', 'Summarize the following content in a clear and concise way. Highlight the key points.', 'general', true),
    ('SQL Query', 'Help write SQL queries', 'Help me write a SQL query for the following requirement. Explain your approach.', 'database', false),
    ('Debug', 'Help debug an issue', 'Help me debug this issue. Analyze the error and suggest potential fixes.', 'coding', true)
ON CONFLICT DO NOTHING;

-- ========================
-- DONE
-- ========================
SELECT 'Chat history tables created successfully!' AS status;
