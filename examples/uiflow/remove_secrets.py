import json
import re
import sys
from xml.etree import ElementTree as ET


def remove_secrets(filename):
    # Reading the contents of the file
    with open(filename, "r") as file:
        file_contents = file.read()

    # Replacing the secrets using regular expressions
    modified_content = re.sub(r"api_key=\w+", "api_key=API_KEY", file_contents)
    modified_content = re.sub(r"item_id=[a-f0-9\-]+", "item_id=ITEM_ID", modified_content)
    modified_content = re.sub(r"location_id=[a-f0-9\-]+", "location_id=LOCATION_ID", modified_content)

    # Replacing the "apikey" value with an empty string
    modified_content = re.sub(r'("apikey":")\w+(")', r"\1\2", modified_content)

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
