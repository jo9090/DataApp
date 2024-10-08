# -*- coding: utf-8 -*-

"""# Import Libraries"""

# Import Libraries
from langchain.document_loaders import DirectoryLoader, PyMuPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Weaviate
import weaviate
from langchain.schema import Document
from langchain.document_loaders.image import UnstructuredImageLoader
from langchain.document_loaders.csv_loader import CSVLoader
from langchain.chains.question_answering import load_qa_chain
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI
import os
from pydub import AudioSegment
import speech_recognition as sr

"""# Get the API Secretes"""

# Get the secrets
from google.colab import drive, userdata
drive.mount('/content/drive')

OPENAI_API_KEY = userdata.get('OPENAI_API_KEY')
WEAVIATE_API_KEY = userdata.get('WEAVIATE_API_KEY')
WEAVIATE_URL = userdata.get('WEAVIATE_URL')
YOUTUBE_URL = userdata.get('YOUTUBE_URL')

if OPENAI_API_KEY:
    print("OpenAI API key retrieved successfully")
else:
    print("OpenAI API key not found in Colab secrets")

if WEAVIATE_API_KEY:
    print("Weaviate API key retrieved successfully")
else:
    print("Weaviate API key not found in Colab secrets")

if WEAVIATE_URL:
    print("Weaviate URL retrieved successfully")
else:
    print("Weaviate URL not found in Colab secrets")

if YOUTUBE_URL:
    print("YOUTUBE URL retrieved successfully")
else:
    print("YOUTUBE URL not found in Colab secrets")

"""# Import Packages to Load Documents"""

# Import Load document packages
from langchain.document_loaders import (
    DirectoryLoader,
    UnstructuredImageLoader,
    PyMuPDFLoader,
    CSVLoader,
    YoutubeLoader
)
from langchain.document_loaders.image import UnstructuredImageLoader
from langchain.document_loaders.csv_loader import CSVLoader

"""# Define the laoders for the data"""

# Define loaders for different modalities
text_loader = DirectoryLoader('/content/drive/MyDrive/Dallas AI/rag/text/', glob="**/*.txt", loader_cls=PyMuPDFLoader)
pdf_loader = DirectoryLoader('/content/drive/MyDrive/Dallas AI/rag/text/', glob="**/*.pdf", loader_cls=PyMuPDFLoader)
image_loader = DirectoryLoader('/content/drive/MyDrive/Dallas AI/rag/images/', glob="**/*.{png,jpg,jpeg}", loader_cls=UnstructuredImageLoader)
csv_loader = DirectoryLoader('/content/drive/MyDrive/Dallas AI/rag/tables/', glob="**/*.csv", loader_cls=CSVLoader)
video_loader = YoutubeLoader.from_youtube_url(YOUTUBE_URL, add_video_info=True)

# Load data from each modality
text_data = text_loader.load()
pdf_data = pdf_loader.load()
image_data = image_loader.load()
csv_data = csv_loader.load()
video_data = video_loader.load()

print(f"Number of text documents: {len(text_data)}")
print(f"Number of text documents: {len(pdf_data)}")
print(f"Number of image documents: {len(image_data)}")
print(f"Number of CSV documents: {len(csv_data)}")
print(f"Number of video documents: {len(video_data)}")

"""# Combine all the data into one
# i.e all_data
"""

# Combine all data
all_data = text_data + pdf_data + image_data + csv_data + video_data

all_data

"""# Data Splitting
# Split the data (all_data) into chunks
"""

# Split text documents into chunks
from langchain.text_splitter import RecursiveCharacterTextSplitter

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=20)
all_docs = text_splitter.split_documents(all_data)

all_docs

"""# Embeddings
# Embedding Conversions
"""

# Set the API key as an environment variable
os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY

# Create the embeddings object
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

embeddings

"""# Weaviate Vector Database Connection
# Connect to Weaviate Vector Database to store data in vector store
"""

# Weaviate Vector Database Connection
import weaviate
from langchain.vectorstores import Weaviate

auth_config = weaviate.auth.AuthApiKey(api_key=WEAVIATE_API_KEY)

client = weaviate.Client(
    url=WEAVIATE_URL,
    additional_headers={"X-OpenAI-Api-key": OPENAI_API_KEY},
    auth_client_secret=auth_config,
    startup_period=10
)

# Check if your instance is live and ready
# This should return `True`
client.is_ready()

"""# Schema for Multimodal Data"""

# Define schema for multimodal data
client.schema.delete_class('MultimodalExample')

schema = {
    "classes": [
        {
            "class": "MultimodalExample",
            "vectorizer": "text2vec-openai",
            "properties": [
                {
                    "dataType": ["text"],
                    "name": "content"
                },
                {
                    "dataType": ["text"],
                    "name": "source"
                },
                {
                    "dataType": ["text"],
                    "name": "type"
                }
            ]
        }
    ]
}

client.schema.create(schema)

client.data_object.get()

"""# Vector Store
# Load Text data into Vector Store
"""

# Be patient and wait! This takes a few minutes to load
# Initialize the Weaviate vectorstore
vectorstore = Weaviate(client, index_name="MultimodalExample", text_key="text")


# Code 1: Load individual documents
for doc in all_docs:
    vectorstore.add_texts(
        texts=[doc.page_content],
        metadatas=[{"source": doc.metadata.get("source", ""), "type": doc.metadata.get("type", "")}]
    )

# Code 2: Load additional documents in bulk
text_meta_pair = [(doc.page_content, doc.metadata) for doc in all_docs]
texts, meta = list(zip(*text_meta_pair))
vectorstore.add_texts(texts, meta)

vectorstore

doc

all_docs

"""# Score the closeness of the vectors for the stored documents"""

def query_weaviate(query, collection_name):

    nearText = {
        "concepts": [query],
        "distance": 0.7,
    }

    properties = [
        "title", "content", "url",
        "_additional {certainty distance}"
    ]

    result = (
        client.query
        .get(collection_name, properties)
        .with_near_text(nearText)
        .with_limit(10)
        .do()
    )

    # Check for errors
    if ("errors" in result):
        print ("\033[91mYou probably have run out of OpenAI API calls for the current minute – the limit is set at 60 per minute.")
        raise Exception(result["errors"][0]['message'])

    return result["data"]["Get"][collection_name]

query_result = query_weaviate("all_docs", "Article")

for i, article in enumerate(query_result):
    print(f"{i+1}. { article['title']} (Score: {round(article['_additional']['certainty'],3) })")

"""#Initialize the Q&A chain"""

from langchain_openai import OpenAI

# define chain
chain = load_qa_chain(
    OpenAI(openai_api_key = OPENAI_API_KEY,temperature=0),
    chain_type="stuff")

"""# Similarity Search
# This searches for vectors (data) that are similar in the vectorstore
"""

query = "what is a Transformer?"

# retrieve text related to the  query
docs = vectorstore.similarity_search(query, top_k=2)

# create answer
chain.run(input_documents=docs, question=query)

query = "Why are there two monthly measures of employment?"

# retrieve text related to the query
docs = vectorstore.similarity_search(query, top_k=2)

# create answer
chain.run(input_documents=docs, question=query)

query = "Hurricane Beryl"

# retrieve text related to the query
docs = vectorstore.similarity_search(query, top_k=2)

# create answer
chain.run(input_documents=docs, question=query)

query = "what is the unemployment rate in July"

# retrieve text related to the query
docs = vectorstore.similarity_search(query, top_k=2)

# create answer
chain.run(input_documents=docs, question=query)

query = "Health care added how many jobs in July"

# retrieve text related to the query
docs = vectorstore.similarity_search(query, top_k=2)

# create answer
chain.run(input_documents=docs, question=query)

query = "What is Encoder"

# retrieve text related to the query
docs = vectorstore.similarity_search(query, top_k=2)

# create answer
chain.run(input_documents=docs, question=query)

query = "Comparison of All Employee Average Weekly Hours, Seasonally Adjusted, before and after the March 2023 Benchmark"

# retrieve text related to the query
docs = vectorstore.similarity_search(query, top_k=2)

# create answer
chain.run(input_documents=docs, question=query)

query = "What is the Current Employment Statistics Summary, July 2024"

# retrieve text related to the query
docs = vectorstore.similarity_search(query, top_k=2)

# create answer
chain.run(input_documents=docs, question=query)

query = "RAG Architecture Explained: Practical Example in 5 Minutes"

# retrieve text related to the query
docs = vectorstore.similarity_search(query, top_k=2)

# create answer
chain.run(input_documents=docs, question=query)