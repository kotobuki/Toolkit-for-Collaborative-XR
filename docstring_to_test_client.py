import ast
import json
import re
import sys


def docstring_to_array(python_file):
    with open(python_file, "r") as source:
        tree = ast.parse(source.read())
    api_dict = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            docstring = ast.get_docstring(node)
            if (
                docstring
                and not docstring.startswith("INTERNAL_FUNCTION")
                and not docstring.startswith("NOT_YET_IMPLEMENTED")
            ):
                docstring_lines = docstring.split("\n")
                description = docstring_lines[0].strip()
                parameters = []
                response = None
                in_response_section = False
                for line in docstring_lines[1:]:
                    line = line.strip()
                    if line.startswith("-") and not in_response_section:
                        split_result = re.split(r"\(.*?\): ", line[1:].strip(), maxsplit=1)
                        if len(split_result) == 2:
                            param_name, param_description = split_result

                            # Ignore the api_key parameter
                            if param_name.strip() != "api_key":
                                parameters.append([param_name.strip(), param_description])

                    # If we're in the response section, we're done
                    elif line.startswith("Response"):
                        in_response_section = True
                api_dict[f"/{node.name}"] = {
                    "method": "GET",
                    "parameters": parameters,
                    "description": description,
                }
    return api_dict


# Base HTML structure with a JavaScript section
base_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Client</title>
    <style>
        body {{
            font-family: Roboto, monospace;
        }}
        input[type="text"] {{
            font-family: Roboto, monospace;
        }}
        .endpoint {{
            margin-bottom: 20px;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .endpoint input[type="text"] {{
            margin-bottom: 10px;
            padding: 5px;
            width: 100%;
        }}
    </style>
</head>
<body>
    <h1>Settings</h1>
    
    <div>
        <label for="base_url">Base URL:</label>
        <input type="text" id="base_url" name="base_url" size="40">
    </div>

    <div>
        <label for="apiKeyDesigner">API Key (Designer):</label>
        <input type="text" id="apiKeyDesigner" name="apiKeyDesigner" size="30">
    </div>

    <div>
        <label for="apiKeyPlayer">API Key (Player):</label>
        <input type="text" id="apiKeyPlayer" name="apiKeyPlayer" size="30">
    </div>

    <div>
        <label for="apiKeySensor">API Key (Sensor):</label>
        <input type="text" id="apiKeySensor" name="apiKeySensor" size="30">
    </div>

    <div>
        <label for="apiKeyActuator">API Key (Actuator):</label>
        <input type="text" id="apiKeyActuator" name="apiKeyActuator" size="30">
    </div>

    <div>
        <p>Role:</p>
        <input type="radio" id="roleDesigner" name="role" value="designer">
        <label for="roleDesigner">Designer</label><br>
        <input type="radio" id="rolePlayer" name="role" value="player">
        <label for="rolePlayer">Player</label><br>
        <input type="radio" id="roleSensor" name="role" value="sensor">
        <label for="roleSensor">Sensor</label><br>
        <input type="radio" id="roleActuator" name="role" value="actuator">
        <label for="roleActuator">Actuator</label><br>
    </div>
    
    <h1>Endpoints</h1>
    <!-- For each endpoint -->
    {endpoints}
    
    <script>
        function submitRequest(endpoint) {{
            var base_url = document.getElementById('base_url').value;
            var api_key = getApiKey();
            var url = base_url + endpoint;
            var param_string = "?api_key=" + api_key;
            var parameters = document.getElementsByClassName(endpoint + '_param');
            for (var i = 0; i < parameters.length; i++) {{
                if (parameters[i].value != '') {{
                    param_string += '&' + parameters[i].name + '=' + encodeURIComponent(parameters[i].value);
                }}
            }}
            var full_url = url + param_string;
            document.getElementById(endpoint + '_url').innerText = 'Generated URL:\\n' + full_url;
            var startTime = Date.now();
            fetch(full_url)
                .then(response => {{
                        var endTime = Date.now();
                        var responseTime = endTime - startTime;
                        return response.text().then(text => ({{
                            text: text,
                            status: response.status,
                            statusText: response.statusText,
                            responseTime: responseTime
                        }}));
                    }})
                    .then(data => {{
                        document.getElementById(endpoint + '_result').innerText = 
                            'Result:\\n' + data.text + '\\n' + 
                            data.status + ' ' + data.statusText + 
                            ' (' + data.responseTime + ' ms)';
                    }})
                    .catch((error) => {{
                        document.getElementById(endpoint + '_result').innerText = 'Error:\\n' + error;
                    }});
            }}

        function getApiKey() {{
            var role = document.querySelector('input[name="role"]:checked').value;
            return document.getElementById('apiKey' + role.charAt(0).toUpperCase() + role.slice(1)).value;
        }}
    </script>
</body>
</html>
"""


# Endpoint HTML structure
endpoint_html = """
<div class="endpoint">
    <h2>{endpoint_name}</h2>
    <p>{description}</p>
    {inputs}
    <button type="button" onclick="submitRequest('{endpoint_name}')">Submit</button>
    <p id="{endpoint_name}_url"></p>
    <p id="{endpoint_name}_result"></p>
</div>
"""


if __name__ == "__main__":
    filename = sys.argv[1]

    # Get endpoints from Python file
    endpoints = docstring_to_array(filename)

    # Generate HTML for each endpoint
    endpoint_htmls = ""
    for endpoint_name, endpoint_details in endpoints.items():
        # Skip endpoints with no parameters
        # if endpoint_details["parameters"].__len__() < 1:
        #     continue

        inputs = "\n".join(
            [
                f'<label for="{endpoint_name}_{param[0]}">{param[0]}: {param[1]}</label><input type="text" id="{endpoint_name}_{param[0]}" name="{param[0]}" class="{endpoint_name}_param">'
                for param in endpoint_details["parameters"]
            ]
        )
        endpoint_htmls += endpoint_html.format(
            endpoint_name=endpoint_name, description=endpoint_details["description"], inputs=inputs
        )

    # Insert endpoint HTML into base HTML
    full_html = base_html.format(endpoints=endpoint_htmls)

    with open("test_client.html", "w") as f:
        f.write(full_html)
