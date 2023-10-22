import json
import re
import sys
from xml.etree import ElementTree as ET


def remove_secrets(filename):
    # Reading the contents of the file
    with open(filename, "r") as file:
        file_contents = file.read()

    # Replacing the "apikey" value with an empty string
    modified_content = re.sub(r'("apikey":")\w+(")', r"\1\2", file_contents)

    # Replacing the "uuid" value with an empty string
    modified_content = re.sub(r'("uuid":")[a-f0-9\-]+(")', r"\1\2", modified_content)

    # Parsing the modified content as JSON and extracting the "blockly" key which contains the XML content
    parsed_json = json.loads(modified_content)
    blockly_xml_content = parsed_json.get("blockly", "")

    # Parsing the XML content
    root = ET.fromstring(f"<root>{blockly_xml_content}</root>")

    # Finding the "wifi_doConnect" block and replacing the SSID and Password
    for block in root.findall(".//block[@type='wifi_doConnect']"):
        ssid_field = block.find(".//value[@name='apiKey']/shadow/field[@name='TEXT']")
        if ssid_field is not None:
            ssid_field.text = "WIFI_SSID"

        password_field = block.find(".//value[@name='Msg']/shadow/field[@name='TEXT']")
        if password_field is not None:
            password_field.text = "WIFI_PASSWORD"

    # Replacing the base URL with a placeholder text
    for block in root.findall(".//block[@type='variables_set']"):
        url_field = block.find("./field[@name='VAR']")
        if url_field is not None and url_field.text == "URL":
            base_url_field = block.find(".//value[@name='VALUE']/block/field[@name='TEXT']")
            if base_url_field is not None and base_url_field.text.startswith("https://"):
                base_url_field.text = "BASE_URL"

    # Replacing the project specific values with placeholders
    for block in root.findall(".//block[@type='text_add']"):
        # For ?api_key=
        api_key_field = block.find(".//value[@name='arg0']/shadow/field[@name='TEXT']")
        if api_key_field is not None and api_key_field.text == "?api_key=":
            secret_field = block.find(".//value[@name='arg1']/block/field[@name='TEXT']")
            if secret_field is not None:
                secret_field.text = "API_KEY"

        # For &item_id=
        item_id_field = block.find(".//value[@name='arg0']/shadow/field[@name='TEXT']")
        if item_id_field is not None and item_id_field.text == "&item_id=":
            secret_field = block.find(".//value[@name='arg1']/block/field[@name='TEXT']")
            if secret_field is not None:
                secret_field.text = "ITEM_ID"

    # Converting the XML back to string
    cleaned_blockly_xml = ET.tostring(root, encoding="unicode").replace("<root>", "").replace("</root>", "")
    parsed_json["blockly"] = cleaned_blockly_xml

    # Saving the modified content to a new file
    new_filename = filename.rsplit(".", 1)[0] + "_cleaned." + filename.rsplit(".", 1)[1]
    with open(new_filename, "w") as file:
        file.write(json.dumps(parsed_json))

    print(f"Processed file saved as {new_filename}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please provide the filename as an argument.")
        sys.exit(1)

    filename = sys.argv[1]
    remove_secrets(filename)
