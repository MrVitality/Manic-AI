#!/usr/bin/env python3
"""
Manic AI - Qdrant Vector Database Setup
Creates collections for RAG document storage
"""

import requests
import json
import sys

# Configuration
QDRANT_URL = "http://100.111.244.124:6333"
VECTOR_DIMENSION = 768  # nomic-embed-text dimension

# Collection configurations
COLLECTIONS = [
    {
        "name": "documents",
        "description": "General document storage for RAG",
        "vectors": {
            "size": VECTOR_DIMENSION,
            "distance": "Cosine"
        }
    },
    {
        "name": "code",
        "description": "Code snippets and documentation",
        "vectors": {
            "size": VECTOR_DIMENSION,
            "distance": "Cosine"
        }
    },
    {
        "name": "conversations",
        "description": "Chat history for context retrieval",
        "vectors": {
            "size": VECTOR_DIMENSION,
            "distance": "Cosine"
        }
    },
    {
        "name": "knowledge_base",
        "description": "Curated knowledge articles",
        "vectors": {
            "size": VECTOR_DIMENSION,
            "distance": "Cosine"
        }
    }
]


def check_qdrant_health():
    """Check if Qdrant is accessible"""
    try:
        response = requests.get(f"{QDRANT_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ Qdrant is healthy")
            return True
    except requests.exceptions.RequestException as e:
        print(f"✗ Cannot connect to Qdrant: {e}")
    return False


def list_collections():
    """List existing collections"""
    try:
        response = requests.get(f"{QDRANT_URL}/collections")
        if response.status_code == 200:
            collections = response.json().get("result", {}).get("collections", [])
            return [c["name"] for c in collections]
    except Exception as e:
        print(f"Error listing collections: {e}")
    return []


def create_collection(name: str, vectors_config: dict, description: str = ""):
    """Create a new Qdrant collection"""

    payload = {
        "vectors": vectors_config,
        "optimizers_config": {
            "default_segment_number": 2,
            "indexing_threshold": 10000
        },
        "replication_factor": 1,
        "write_consistency_factor": 1
    }

    try:
        response = requests.put(
            f"{QDRANT_URL}/collections/{name}",
            headers={"Content-Type": "application/json"},
            json=payload
        )

        if response.status_code in [200, 201]:
            print(f"✓ Created collection: {name}")
            return True
        elif response.status_code == 409:
            print(f"• Collection already exists: {name}")
            return True
        else:
            print(f"✗ Failed to create {name}: {response.text}")
            return False

    except Exception as e:
        print(f"✗ Error creating collection {name}: {e}")
        return False


def create_payload_index(collection_name: str, field_name: str, field_type: str):
    """Create payload index for filtering"""

    payload = {
        "field_name": field_name,
        "field_schema": field_type
    }

    try:
        response = requests.put(
            f"{QDRANT_URL}/collections/{collection_name}/index",
            headers={"Content-Type": "application/json"},
            json=payload
        )

        if response.status_code in [200, 201]:
            print(f"  ✓ Created index: {collection_name}.{field_name}")
            return True
        else:
            print(f"  • Index may already exist: {collection_name}.{field_name}")
            return True

    except Exception as e:
        print(f"  ✗ Error creating index: {e}")
        return False


def setup_collections():
    """Main setup function"""

    print("=" * 60)
    print("Manic AI - Qdrant Setup")
    print("=" * 60)
    print()

    # Check health
    if not check_qdrant_health():
        print("\nPlease ensure Qdrant is running and accessible.")
        sys.exit(1)

    print()

    # Get existing collections
    existing = list_collections()
    print(f"Existing collections: {existing if existing else 'None'}")
    print()

    # Create collections
    print("Creating collections...")
    print("-" * 40)

    for config in COLLECTIONS:
        create_collection(
            name=config["name"],
            vectors_config=config["vectors"],
            description=config["description"]
        )

        # Create common payload indexes for filtering
        create_payload_index(config["name"], "user_id", "keyword")
        create_payload_index(config["name"], "collection_id", "keyword")
        create_payload_index(config["name"], "document_id", "keyword")
        create_payload_index(config["name"], "created_at", "datetime")

    print()
    print("-" * 40)

    # Verify
    final_collections = list_collections()
    print(f"\nFinal collections: {final_collections}")
    print()
    print("=" * 60)
    print("Qdrant setup complete!")
    print("=" * 60)
    print()
    print("Dashboard: http://100.111.244.124:6333/dashboard")
    print()


def show_collection_info():
    """Show info about all collections"""

    print("\nCollection Details:")
    print("-" * 60)

    collections = list_collections()

    for name in collections:
        try:
            response = requests.get(f"{QDRANT_URL}/collections/{name}")
            if response.status_code == 200:
                info = response.json().get("result", {})
                vectors_count = info.get("vectors_count", 0)
                points_count = info.get("points_count", 0)
                status = info.get("status", "unknown")

                print(f"\n{name}:")
                print(f"  Status: {status}")
                print(f"  Points: {points_count}")
                print(f"  Vectors: {vectors_count}")
        except Exception as e:
            print(f"Error getting info for {name}: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--info":
        show_collection_info()
    else:
        setup_collections()
        show_collection_info()
