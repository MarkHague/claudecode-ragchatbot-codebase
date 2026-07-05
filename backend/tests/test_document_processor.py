import pytest
from document_processor import DocumentProcessor


pytestmark = pytest.mark.unit


SAMPLE_DOC = """Course Title: Building RAG Systems
Course Link: https://example.com/course
Course Instructor: Jane Doe

Lesson 1: Introduction
Lesson Link: https://example.com/lesson1
This lesson introduces retrieval-augmented generation. It combines search with language models.

Lesson 2: Advanced Topics
Lesson Link: https://example.com/lesson2
This lesson covers chunking strategies and embeddings in depth.
"""


@pytest.fixture
def doc_path(tmp_path):
    path = tmp_path / "course.txt"
    path.write_text(SAMPLE_DOC, encoding="utf-8")
    return str(path)


def test_process_course_document_extracts_metadata(doc_path):
    processor = DocumentProcessor(chunk_size=800, chunk_overlap=100)
    course, chunks = processor.process_course_document(doc_path)

    assert course.title == "Building RAG Systems"
    assert course.course_link == "https://example.com/course"
    assert course.instructor == "Jane Doe"


def test_process_course_document_extracts_lessons(doc_path):
    processor = DocumentProcessor(chunk_size=800, chunk_overlap=100)
    course, _ = processor.process_course_document(doc_path)

    assert len(course.lessons) == 2
    assert course.lessons[0].lesson_number == 1
    assert course.lessons[0].title == "Introduction"
    assert course.lessons[0].lesson_link == "https://example.com/lesson1"
    assert course.lessons[1].lesson_number == 2


def test_process_course_document_creates_chunks_tagged_with_course_and_lesson(doc_path):
    processor = DocumentProcessor(chunk_size=800, chunk_overlap=100)
    course, chunks = processor.process_course_document(doc_path)

    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.course_title == course.title
    assert chunks[0].lesson_number == 1
    assert "Lesson 1 content:" in chunks[0].content


def test_chunk_text_respects_chunk_size():
    processor = DocumentProcessor(chunk_size=50, chunk_overlap=0)
    text = "First sentence here. Second sentence follows. Third one arrives. Fourth is last."
    chunks = processor.chunk_text(text)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 50 or " " not in chunk


def test_chunk_text_returns_single_chunk_for_short_text():
    processor = DocumentProcessor(chunk_size=800, chunk_overlap=100)
    chunks = processor.chunk_text("Just one short sentence.")
    assert chunks == ["Just one short sentence."]
