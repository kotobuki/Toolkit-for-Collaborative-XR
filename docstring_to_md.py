import ast
import re
import sys


def generate_comparison_table_of_roles(source_code_content):
    """
    Generate a comparison table based on docstrings in Flask app source code, ignoring
    endpoints with docstrings containing NOT_YET_IMPLEMENTED anywhere.

    Parameters:
    - source_code_content: str, The source code of the Flask application

    Returns:
    - str, The comparison table in Markdown format
    """
    # Extracting Flask routes (endpoints) and their associated docstrings
    endpoint_pattern = r'@app.route\("(/.+?)", methods=.+?\)(?:\s+?@.+?\s+?)?def (.+?):\s+?"""\s+?(.+?)\s+?"""'
    matches = re.findall(endpoint_pattern, source_code_content, re.DOTALL)
    docstrings_by_endpoint = {
        match[0]: match[2]
        for match in matches
        if "NOT_YET_IMPLEMENTED" not in match[2] and not match[2].startswith("INTERNAL_FUNCTION")
    }

    # Roles and API keys to check for
    roles = ["DESIGNER", "PLAYER", "SENSOR", "ACTUATOR"]

    # Extracting roles associated with each endpoint based on API keys in the docstrings
    roles_by_endpoint_from_docstrings = {}
    for endpoint, docstring in docstrings_by_endpoint.items():
        roles_for_endpoint = []
        for role in roles:
            api_key_pattern_for_role = f"API_KEY_{role}"
            if api_key_pattern_for_role in docstring:
                roles_for_endpoint.append(role)
        roles_by_endpoint_from_docstrings[endpoint] = roles_for_endpoint

    # Creating the comparison table in Markdown format
    table_header = "| Endpoint | Designer | Player | Sensor | Actuator |"
    table_separator = "| --- | --- | --- | --- | --- |"
    table_rows_from_docstrings = []
    for endpoint, roles_for_endpoint in roles_by_endpoint_from_docstrings.items():
        row = [endpoint]
        for role in roles:
            if role in roles_for_endpoint:
                row.append("✔")
            else:
                row.append("")
        table_rows_from_docstrings.append("| " + " | ".join(row) + " |")
    return "\n".join([table_header, table_separator] + table_rows_from_docstrings)


def generate_endpoint_documentation(source_code_content):
    """
    Generate documentation for each endpoint based on docstrings in Flask app source code,
    ignoring endpoints with docstrings containing NOT_YET_IMPLEMENTED anywhere.

    Parameters:
    - source_code_content: str, The source code of the Flask application

    Returns:
    - str, The documentation in Markdown format
    """
    tree = ast.parse(source_code_content)
    markdown = ""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            docstring = ast.get_docstring(node)
            if (
                docstring
                and not docstring.startswith("INTERNAL_FUNCTION")
                and not docstring.startswith("NOT_YET_IMPLEMENTED")
            ):
                # Add backticks around the first part of each list item
                docstring = re.sub(r"- ([\w\s]+?)(?=\s\()", r"- `\1`", docstring)
                # Add backticks around words that consist of capital letters plus one underscore or at least five capital letters
                docstring = re.sub(r"\b([A-Z_]{6,}|[A-Z]{5,})\b", r"`\1`", docstring)
                markdown += f"### `/{node.name}`\n\n"
                markdown += f"{docstring}\n\n"
    return markdown


if __name__ == "__main__":
    filename = sys.argv[1]
    with open(filename, "r") as source:
        source_code_content = source.read()

        markdown = "# API Documentation\n\n"
        markdown += "## Roles\n\n"
        markdown += generate_comparison_table_of_roles(source_code_content)
        markdown += "\n\n"
        markdown += "## Endpoints\n\n"
        markdown += generate_endpoint_documentation(source_code_content)

        with open("api_documentation.md", "w") as md_file:
            md_file.write(markdown.rstrip() + "\n")
