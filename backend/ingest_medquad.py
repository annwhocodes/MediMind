
import os
import sys
import glob
import pandas as pd
import chromadb
from chromadb.config import Settings
import logging
import kagglehub
import shutil
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure Kaggle credentials are available to the library
# Ensure Kaggle credentials are available to the library
if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"):
    os.environ["KAGGLE_USERNAME"] = os.getenv("KAGGLE_USERNAME")
    key = os.getenv("KAGGLE_KEY")
    if key and key.startswith("KGAT_"):
        key = key.replace("KGAT_", "")
    os.environ["KAGGLE_KEY"] = key

    # Also support KAGGLE_API_TOKEN if that was the intended var
    if os.getenv("KAGGLE_API_TOKEN"):
         token = os.getenv("KAGGLE_API_TOKEN")
         if token and token.startswith("KGAT_"):
             token = token.replace("KGAT_", "")
         os.environ["KAGGLE_KEY"] = token

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ingest_medquad():
    """
    Downloads MedQuAD dataset from Kaggle, preprocesses it, and ingests it into ChromaDB.
    """
    logger.info("Starting MedQuAD Data Ingestion...")

    # 1. Download Dataset
    try:
        if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"):
            logger.info(f"Using Kaggle Credentials - User: {os.getenv('KAGGLE_USERNAME')}")
        
        logger.info("Downloading MedQuAD dataset from Kaggle (gpreda/medquad)...")
        # specific dataset handle for MedQuad on Kaggle
        dataset_path = kagglehub.dataset_download("gpreda/medquad")
        logger.info(f"Dataset downloaded to: {dataset_path}")
    except Exception as e:
        logger.error(f"Failed to download dataset: {e}")
        print("\n" + "="*40)
        print("AUTHENTICATION ERROR")
        print("To download datasets from Kaggle, you need valid API credentials.")
        print(f"Current User: {os.getenv('KAGGLE_USERNAME')}")
        print(f"Current Key Length: {len(os.getenv('KAGGLE_KEY') or '')}")
        print("="*40 + "\n")
        return

    # 2. Initialize ChromaDB
    try:
        # Path relative to this script: ../agents/medical_vector_store
        current_dir = os.path.dirname(os.path.abspath(__file__))
        chroma_db_path = os.path.abspath(os.path.join(current_dir, "../agents/medical_vector_store"))
        
        logger.info(f"Connecting to ChromaDB at: {chroma_db_path}")
        
        client = chromadb.PersistentClient(path=chroma_db_path)
        
        # Get or create collection
        collection_name = "medical_knowledge"
        collection = client.get_or_create_collection(name=collection_name)
        logger.info(f"Connected to collection: '{collection_name}'")
        logger.info(f"Current collection count: {collection.count()}")
        
    except Exception as e:
        logger.error(f"Failed to initialize ChromaDB: {e}")
        return

    # 3. Process Files (Walker)
    # The dataset structure usually contains CSVs in this version
    csv_files = glob.glob(os.path.join(dataset_path, "**/*.csv"), recursive=True)
    
    if not csv_files:
        logger.warning(f"No CSV files found in {dataset_path}. Checking for other formats...")
        # Check for XML if CSVs are missing (folder structure varies)
        # But jpmiller/medquad is typically CSV.
    
    total_records = 0
    batch_size = 100
    
    documents = []
    metadatas = []
    ids = []
    
    logger.info(f"Found {len(csv_files)} CSV files. Starting processing...")

    for file_path in csv_files:
        try:
            # Read CSV
            df = pd.read_csv(file_path)
            
            # Check necessary columns
            # Common columns in MedQuAD csvs: 'question', 'answer', 'source', 'focus_area'
            # Let's normalize column names
            df.columns = [c.lower().strip() for c in df.columns]
            
            if 'question' not in df.columns or 'answer' not in df.columns:
                logger.warning(f"Skipping {os.path.basename(file_path)}: Missing 'question' or 'answer' columns.")
                continue
                
            for _, row in df.iterrows():
                question = str(row.get('question', '')).strip()
                answer = str(row.get('answer', '')).strip()
                source = str(row.get('source', 'MedQuAD'))
                focus = str(row.get('focus_area', 'General'))
                
                if not question or not answer:
                    continue
                
                # Create text chunk for RAG
                text_chunk = f"Question: {question}\nAnswer: {answer}"
                
                documents.append(text_chunk)
                metadatas.append({
                    "source": source,
                    "focus": focus,
                    "type": "medical_qa"
                })
                # Create unique ID based on hash or index
                ids.append(f"medquad_{total_records}")
                
                total_records += 1
                
                # Batch Ingest
                if len(documents) >= batch_size:
                    collection.upsert(
                        documents=documents,
                        metadatas=metadatas,
                        ids=ids
                    )
                    documents = []
                    metadatas = []
                    ids = []
                    if total_records % 1000 == 0:
                        logger.info(f"Processed {total_records} records...")
                        
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")

    # Process remaining batch
    if documents:
        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
    logger.info("="*30)
    logger.info(f"Ingestion Complete!")
    logger.info(f"Total Records Added: {total_records}")
    logger.info(f"Final Collection Count: {collection.count()}")
    logger.info("="*30)

if __name__ == "__main__":
    ingest_medquad()
