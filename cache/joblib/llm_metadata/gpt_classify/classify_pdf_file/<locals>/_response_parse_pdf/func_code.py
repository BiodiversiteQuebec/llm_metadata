# first line: 465
    @memory.cache
    def _response_parse_pdf(parameters_json_dump: str, file_id: str) -> dict:
        client = OpenAI()
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "file_id": file_id
                        },
                        {
                            "type": "input_text",
                            "text": "Extract the biodiversity dataset features from this scientific paper PDF according to the schema."
                        }
                    ]
                }
            ],
            text_format=text_format,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return response.model_dump()
