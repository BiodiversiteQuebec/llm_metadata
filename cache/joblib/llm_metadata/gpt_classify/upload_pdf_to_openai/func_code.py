# first line: 339
@memory.cache
def upload_pdf_to_openai(
    pdf_path: Union[str, Path],
    purpose: str = "user_data"
) -> str:
    """
    Upload a PDF file to OpenAI's File API.

    Args:
        pdf_path: Path to PDF file
        purpose: Purpose for the file upload (default: "user_data")

    Returns:
        File ID from OpenAI

    Note:
        Files are automatically deleted by OpenAI after a retention period.
        For production use, consider implementing file cleanup.
    """
    pdf_path = Path(pdf_path)

    # Do NOT persistently cache uploads.
    # OpenAI file IDs can expire or be deleted (e.g., via cleanup_file=True),
    # and persisting them across runs causes flaky 404s when reused.
    client = get_openai_client()
    with open(str(pdf_path), "rb") as f:
        file = client.files.create(file=f, purpose=purpose)
    return file.id
