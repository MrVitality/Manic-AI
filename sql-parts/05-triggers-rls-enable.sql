-- =============================================================================
-- PART 5: TRIGGERS AND RLS POLICIES
-- Run after Part 4
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Drop existing triggers safely
-- -----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON public.user_profiles;
DROP TRIGGER IF EXISTS update_document_metadata_updated_at ON public.document_metadata;
DROP TRIGGER IF EXISTS update_rag_pipeline_state_updated_at ON public.rag_pipeline_state;
DROP TRIGGER IF EXISTS update_rag_documents_updated_at ON rag.documents;
DROP TRIGGER IF EXISTS update_rag_collections_updated_at ON rag.collections;
DROP TRIGGER IF EXISTS update_rag_conversations_updated_at ON rag.conversations;

-- -----------------------------------------------------------------------------
-- Create Triggers
-- -----------------------------------------------------------------------------

-- Auto-create user profile on signup
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Update timestamps on public tables
CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

CREATE TRIGGER update_document_metadata_updated_at
    BEFORE UPDATE ON public.document_metadata
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

CREATE TRIGGER update_rag_pipeline_state_updated_at
    BEFORE UPDATE ON public.rag_pipeline_state
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

-- Update timestamps on rag tables
CREATE TRIGGER update_rag_documents_updated_at
    BEFORE UPDATE ON rag.documents
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

CREATE TRIGGER update_rag_collections_updated_at
    BEFORE UPDATE ON rag.collections
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

CREATE TRIGGER update_rag_conversations_updated_at
    BEFORE UPDATE ON rag.conversations
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

-- -----------------------------------------------------------------------------
-- Enable RLS on all tables
-- -----------------------------------------------------------------------------
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rag_pipeline_state ENABLE ROW LEVEL SECURITY;

ALTER TABLE rag.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.document_collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.messages ENABLE ROW LEVEL SECURITY;

-- Verify triggers
SELECT trigger_name, event_object_table 
FROM information_schema.triggers 
WHERE trigger_schema IN ('public', 'rag')
ORDER BY event_object_table;
