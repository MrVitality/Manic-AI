-- =============================================================================
-- PART 6: RLS POLICIES - PUBLIC SCHEMA
-- Run after Part 5
-- =============================================================================

-- -----------------------------------------------------------------------------
-- User Profiles Policies
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Admins can view all profiles" ON public.user_profiles;
DROP POLICY IF EXISTS "Admins can update all profiles" ON public.user_profiles;
DROP POLICY IF EXISTS "Only admins can change admin status" ON public.user_profiles;
DROP POLICY IF EXISTS "Service role full access to user_profiles" ON public.user_profiles;
DROP POLICY IF EXISTS "Deny delete for user_profiles" ON public.user_profiles;

CREATE POLICY "Users can view own profile" ON public.user_profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON public.user_profiles
    FOR UPDATE USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id AND is_admin IS NOT DISTINCT FROM FALSE);

CREATE POLICY "Admins can view all profiles" ON public.user_profiles
    FOR SELECT USING (public.is_admin());

CREATE POLICY "Admins can update all profiles" ON public.user_profiles
    FOR UPDATE USING (public.is_admin());

CREATE POLICY "Only admins can change admin status" ON public.user_profiles
    FOR UPDATE TO authenticated
    USING (public.is_admin())
    WITH CHECK (public.is_admin());

CREATE POLICY "Service role full access to user_profiles" ON public.user_profiles
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Deny delete for user_profiles" ON public.user_profiles 
    FOR DELETE USING (false);

-- -----------------------------------------------------------------------------
-- Requests Policies
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own requests" ON public.requests;
DROP POLICY IF EXISTS "Users can insert own requests" ON public.requests;
DROP POLICY IF EXISTS "Admins can view all requests" ON public.requests;
DROP POLICY IF EXISTS "Service role full access to requests" ON public.requests;
DROP POLICY IF EXISTS "Deny delete for requests" ON public.requests;

CREATE POLICY "Users can view own requests" ON public.requests
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own requests" ON public.requests
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Admins can view all requests" ON public.requests
    FOR SELECT USING (public.is_admin());

CREATE POLICY "Service role full access to requests" ON public.requests
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Deny delete for requests" ON public.requests 
    FOR DELETE USING (false);

-- -----------------------------------------------------------------------------
-- Agent Conversations Policies
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own conversations" ON public.agent_conversations;
DROP POLICY IF EXISTS "Users can insert own conversations" ON public.agent_conversations;
DROP POLICY IF EXISTS "Users can update own conversations" ON public.agent_conversations;
DROP POLICY IF EXISTS "Admins can view all conversations" ON public.agent_conversations;
DROP POLICY IF EXISTS "Service role full access to agent_conversations" ON public.agent_conversations;
DROP POLICY IF EXISTS "Deny delete for agent_conversations" ON public.agent_conversations;

CREATE POLICY "Users can view own conversations" ON public.agent_conversations
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own conversations" ON public.agent_conversations
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own conversations" ON public.agent_conversations
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all conversations" ON public.agent_conversations
    FOR SELECT USING (public.is_admin());

CREATE POLICY "Service role full access to agent_conversations" ON public.agent_conversations
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Deny delete for agent_conversations" ON public.agent_conversations 
    FOR DELETE USING (false);

-- -----------------------------------------------------------------------------
-- Agent Messages Policies
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own messages" ON public.agent_messages;
DROP POLICY IF EXISTS "Users can insert own messages" ON public.agent_messages;
DROP POLICY IF EXISTS "Admins can view all messages" ON public.agent_messages;
DROP POLICY IF EXISTS "Service role full access to agent_messages" ON public.agent_messages;
DROP POLICY IF EXISTS "Deny delete for agent_messages" ON public.agent_messages;

CREATE POLICY "Users can view own messages" ON public.agent_messages
    FOR SELECT USING (auth.uid() = computed_session_user_id);

CREATE POLICY "Users can insert own messages" ON public.agent_messages
    FOR INSERT WITH CHECK (auth.uid() = computed_session_user_id);

CREATE POLICY "Admins can view all messages" ON public.agent_messages
    FOR SELECT USING (public.is_admin());

CREATE POLICY "Service role full access to agent_messages" ON public.agent_messages
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Deny delete for agent_messages" ON public.agent_messages 
    FOR DELETE USING (false);

-- -----------------------------------------------------------------------------
-- Document Tables Policies (Backend-only)
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Service role access to document_metadata" ON public.document_metadata;
DROP POLICY IF EXISTS "Service role access to document_rows" ON public.document_rows;
DROP POLICY IF EXISTS "Service role access to public documents" ON public.documents;
DROP POLICY IF EXISTS "Service role access to rag_pipeline_state" ON public.rag_pipeline_state;

CREATE POLICY "Service role access to document_metadata" ON public.document_metadata
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role access to document_rows" ON public.document_rows
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role access to public documents" ON public.documents
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role access to rag_pipeline_state" ON public.rag_pipeline_state
    FOR ALL USING (auth.role() = 'service_role');

-- Verify
SELECT schemaname, tablename, policyname 
FROM pg_policies 
WHERE schemaname = 'public'
ORDER BY tablename, policyname;
