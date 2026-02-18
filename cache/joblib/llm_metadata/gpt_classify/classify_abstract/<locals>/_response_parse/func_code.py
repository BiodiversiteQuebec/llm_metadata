# first line: 248
    @memory.cache
    def _response_parse(parameters_json_dump: str) -> dict:
        openai = OpenAI()
        response = openai.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": abstract},
            ],
            text_format=text_format,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return response.model_dump()
