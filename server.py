# import necessary libraries
import json
import math
import os
import re
import uuid
from functools import wraps

from firebase_admin import credentials, firestore
from flask import Flask, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from google.api_core.exceptions import Aborted, DeadlineExceeded
from google.api_core.retry import Retry
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.transaction import Transaction

# Initialize the Flask application
app = Flask(__name__)

# Initialize the rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100000 per day", "10000 per hour"],
    storage_uri="memory://",
)

# Enable CORS
CORS(app)


# Define the custom retry strategy to shorten the timeout period (default is 60 seconds)
custom_retry = Retry(
    predicate=lambda e: isinstance(e, (DeadlineExceeded, Aborted)),
    initial=1.0,  # Initial delay between retries in seconds
    maximum=2.0,  # Maximum delay between retries in seconds
    multiplier=1.5,  # Multiplier applied to delay for each retry
    deadline=5.0,  # Maximum total time for all retries (in seconds)
)


def handle_firestore_errors(func):
    """
    INTERNAL_FUNCTION

    Decorator function that adds error handling for Firestore errors.

    Parameters

    - func (function): The endpoint function to decorate.

    Returns

    - The decorated endpoint function.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Call the endpoint function
            return func(*args, **kwargs)
        except DeadlineExceeded:
            # Handle the timeout error
            return "Timeout error occurred while calling Firestore", 500
        except Exception as e:
            # Handle other exceptions
            return f"Error occurred while calling Firestore: {e}", 500

    return wrapper


# Load the Firestore credentials from the environment variable
config_json = os.environ.get("SERVICE_ACCOUNT_KEY_JSON")
config = json.loads(config_json)
db = firestore.Client.from_service_account_info(config)

# Set the API keys from the environment variables
API_KEY_DESIGNER = os.environ.get("API_KEY_DESIGNER")
API_KEY_PLAYER = os.environ.get("API_KEY_PLAYER")
API_KEY_SENSOR = os.environ.get("API_KEY_SENSOR")
API_KEY_ACTUATOR = os.environ.get("API_KEY_ACTUATOR")


@app.route("/ping", methods=["GET"])
@limiter.exempt
def ping():
    """
    Allows a user to check if the server is running.

    Response

    - status code (integer): HTTP status code (always 200).
    """

    # Return a message indicating that the server is running
    return "pong", 200


def convert_to_number(s):
    """
    INTERNAL_FUNCTION

    Convert a string to a number (int or float).

    Parameters

    - s (string): The string to convert.

    Returns

    - The number (int or float).
    """
    try:
        return int(s)
    except ValueError:
        return float(s)


def is_numeric_string(s):
    """
    INTERNAL_FUNCTION

    Check if a string looks like a number (int or float).

    Parameters

    - s (string): The string to check.

    Returns

    - True if the string looks like a number, False otherwise.
    """
    pattern = r"^-?\d+(\.\d+)?$"  # This pattern matches integers and floats (including negative numbers)
    return bool(re.match(pattern, s))


@app.route("/create_item", methods=["GET"])
@handle_firestore_errors
def create_item():
    """
    Allows a designer to create a new item with specific attributes, including a timer and visibility.

    Parameters

    - location_id (string): The location_id of the item.
    - owner (string): The name of the owner of the item, should be either PUBLIC_DOMAIN or A_PLAYER (optional, default is PUBLIC_DOMAIN).
    - name (string): The name of the item (e.g., "flyer", don't have to be unique, can't contain commas).
    - type (string): The type of the item (e.g., FLYER).
    - coordinates (string): The coordinates of the item (x, y, z for an INDOOR location or latitude, longitude for an OUTDOOR location, comma-separated).
    - tags (string): The tags of the item (comma-separated, e.g., "tag1,tag2", optional).
    - attributes (string): The attributes of the item (comma-separated, e.g., "color=blue,shape=circle", optional).
    - api_key (string): The API key for the user (should be API_KEY_DESIGNER).

    Response

    - message (string): A message indicating that the item was created successfully.
    - status code (integer): HTTP status code.
    """
    # Extract parameters from the request
    location_id = request.args.get("location_id")
    owner = request.args.get("owner")
    name = request.args.get("name")
    type = request.args.get("type")
    coordinates = request.args.get("coordinates")
    tags = request.args.get("tags")
    attributes = request.args.get("attributes")
    api_key = request.args.get("api_key")

    # Check if the API key is valid
    if api_key != API_KEY_DESIGNER:
        return "Invalid API key", 400

    # Default to PUBLIC_DOMAIN if owner is not specified
    if owner is None:
        owner = "PUBLIC_DOMAIN"
    else:
        # If specified, check if the owner is valid
        if owner not in ["PUBLIC_DOMAIN", "A_PLAYER"]:
            return "Invalid owner", 400

    # Check if the name is valid (at least one character, can't contain commas)
    if name is None or len(name) == 0 or "," in name:
        return "Invalid name (at least one character, can't contain commas)", 400

    # Check if the type is not empty
    if type is None:
        return "Invalid type", 400

    # Check if the location_id is valid
    if location_id is None:
        return "Invalid location_id", 400
    else:
        # Check if the location_id exists
        locations_ref = db.collection("locations")
        query_ref = locations_ref.where(
            filter=FieldFilter(field_path="location_id", op_string="==", value=location_id)
        )
        locations = query_ref.get(retry=custom_retry)
        if len(locations) == 0:
            return "Invalid location_id", 400

    # Check if the attributes are valid
    if attributes is not None:
        # Check if the attributes are in the correct format
        try:
            attributes = dict(map(lambda x: x.split("="), attributes.split(",")))
        except Exception as e:
            return "Invalid attributes (must be comma-separated key-value pairs)", 400

        # Check if keys and values are valid (can't contain commas, spaces, or equal signs)
        for key, value in attributes.items():
            if "," in key or " " in key or "=" in key:
                return f"Invalid attribute key (can't contain commas, spaces, or equal signs): {key}", 400
            if "," in value or " " in value or "=" in value:
                return f"Invalid attribute value (can't contain commas, spaces, or equal signs): {value}", 400

            # Convert the value to an integer or a float if the value is a number
            if is_numeric_string(value):
                value = convert_to_number(value)

                # Update the value in the attributes dictionary
                attributes[key] = value

    # Check if the coordinates are valid
    if coordinates is None:
        return "Invalid coordinates (you must specify coordinates)", 400
    else:
        # Check if the coordinates are in the correct format
        try:
            coordinates = list(map(float, coordinates.split(",")))
        except Exception as e:
            return "Invalid coordinates (must be comma-separated numbers)", 400

        # Check if the coordinates are in the correct format for the location type
        locations_ref = db.collection("locations")
        query_ref = locations_ref.where(
            filter=FieldFilter(field_path="location_id", op_string="==", value=location_id)
        )
        locations = query_ref.get(retry=custom_retry)
        location = locations[0].to_dict()
        if location["type"] == "INDOOR" and len(coordinates) != 3:
            return "Invalid coordinates (must be x, y, z)", 400
        elif location["type"] == "OUTDOOR" and len(coordinates) != 2:
            return "Invalid coordinates (must be latitude, longitude)", 400

    # Check if the tags are valid
    if tags is not None:
        # Check if the tags are in the correct format
        try:
            tags = tags.split(",")
        except Exception as e:
            return "Invalid tags (must be comma-separated)", 400

        # Check if all the tags are valid
        for tag in tags:
            if len(tag) == 0:
                return "Invalid tags (at least one character)", 400

            # Check if the tag exists
            tags_ref = db.collection("tags")
            query_ref = tags_ref.where(filter=FieldFilter(field_path="name", op_string="==", value=tag))
            found_tags = query_ref.get(retry=custom_retry)
            if len(found_tags) == 0:
                return "Invalid tags (tag does not exist)", 400

    # Generate a unique id for the item
    item_id = str(uuid.uuid4())

    # Create a new item document in Firestore
    doc_ref = db.collection("items").document(item_id)
    doc_ref.set(
        {
            "item_id": item_id,
            "owner": owner,
            "name": name,
            "type": type,
            "location_id": location_id,
            "coordinates": coordinates,
            "tags": tags,
            "attributes": attributes,
        },
        retry=custom_retry,
    )

    # Return a message telling that the item was created successfully
    return f"Item created successfully,{item_id}", 200


@app.route("/delete_item", methods=["GET"])
@handle_firestore_errors
def delete_item():
    """
    Allows a designer to delete an existing item.

    Parameters

    - item_id (string): The id of the item.
    - api_key (string): The API key for the user (should be API_KEY_DESIGNER).

    Response

    - message (string): A message indicating that the item was deleted successfully.
    - status code (integer): HTTP status code.
    """
    # Extract parameters from the request
    item_id = request.args.get("item_id")
    api_key = request.args.get("api_key")

    # Check if the API key is valid
    if api_key != API_KEY_DESIGNER:
        return "Invalid API key", 400

    # Check if the item_id is valid
    if item_id is None:
        return "Invalid item_id", 400
    else:
        # Check if the item_id exists
        items_ref = db.collection("items")
        query_ref = items_ref.where(filter=FieldFilter(field_path="item_id", op_string="==", value=item_id))
        items = query_ref.get(retry=custom_retry)
        if len(items) == 0:
            return "Invalid item_id", 400

    # Delete the item document from Firestore
    doc_ref = db.collection("items").document(item_id)
    doc_ref.delete(retry=custom_retry)

    # Return a message telling that the item was deleted successfully
    return "Item deleted successfully", 200


def item_to_csv(item):
    """
    INTERNAL_FUNCTION

    Converts an item to CSV format.

    Parameters

    - item (Item): The item to convert.

    Returns

    - item_in_csv (string): The item in CSV format.
    """
    # Convert the item to CSV format. Regarding the coordinates, add trailing 0 if the length is 2 (i.e., OUTDOOR location)
    name_str = f'"{item.to_dict()["name"]}"'
    coordinates_csv = ",".join(
        str(item.to_dict()["coordinates"][i]) for i in range(len(item.to_dict()["coordinates"]))
    )
    if len(coordinates_csv.split(",")) == 2:
        coordinates_csv += ",0"

    # If the item has no attributes (i.e., item.to_dict()["attributes"] is None), set the attributes_csv to "null"
    # Otherwise, convert the attributes dictionary to key-value pairs in key=value format and separate them with semicolons
    if item.to_dict()["attributes"] is None or item.to_dict()["attributes"] == {}:
        attributes_str = "null"
    else:
        # Sort the attributes by key and convert the attributes dictionary to key-value pairs in key=value format
        attributes_str = ";".join(
            f"{key}={value}"
            for key, value in sorted(item.to_dict()["attributes"].items(), key=lambda item: item[0])
        )

    item_in_csv = (
        f"{item.id},{name_str},{item.to_dict()['owner']},{item.to_dict()['type']},{coordinates_csv},{attributes_str}\n"
    )
    return item_in_csv


@app.route("/update_item", methods=["GET"])
@handle_firestore_errors
def update_item():
    """
    Allows a designer to update a parameter or parameters of an existing item. At least one parameter must be specified.

    Parameters

    - item_id (string): The id of the item.
    - owner (string): The name of the owner of the item, should be either PUBLIC_DOMAIN or A_PLAYER (optional).
    - name (string): The name of the item (e.g., "flyer", don't have to be unique, optional).
    - type (string): The type of the item (e.g., FLYER, optional).
    - location_id (string): The location_id of the item (optional).
    - coordinates (string): The coordinates of the item (x, y, z for an INDOOR location or latitude, longitude for an OUTDOOR location, comma-separated, optional).
    - tags (string): The tags of the item (comma-separated, e.g., "tag1,tag2", optional).
    - attributes (string): The attributes of the item (comma-separated, e.g., "color=blue,shape=circle", optional). You can increment/decrement an attribute by using the following format: "votes=+1" or "votes=-1".
    - api_key (string): The API key for the user (should be API_KEY_DESIGNER).

    Response

    - message (string): A message indicating that the item was updated successfully.
    - status code (integer): HTTP status code.
    """
    # Extract parameters from the request
    item_id = request.args.get("item_id")
    owner = request.args.get("owner")
    name = request.args.get("name")
    type = request.args.get("type")
    location_id = request.args.get("location_id")
    coordinates = request.args.get("coordinates")
    tags = request.args.get("tags")
    attributes = request.args.get("attributes")
    api_key = request.args.get("api_key")

    # Check if the API key is valid
    if api_key != API_KEY_DESIGNER:
        return "Invalid API key", 400

    # Check if at least one parameter is specified
    if (
        owner is None
        and name is None
        and type is None
        and location_id is None
        and coordinates is None
        and tags is None
        and attributes is None
    ):
        return "At least one parameter must be specified", 400

    # Check if the item_id is valid
    if item_id is None:
        return "Invalid item_id", 400

    # Check if the owner is valid
    if owner is not None and owner not in ["PUBLIC_DOMAIN", "A_PLAYER"]:
        return "Invalid owner (should be either PUBLIC_DOMAIN or A_PLAYER)", 400

    # Create a transaction
    transaction = db.transaction()

    # Use a transaction to update the attribute of the item document in Firestore
    @firestore.transactional
    def update_transaction(transaction):
        # Get the item document from Firestore
        item_ref = db.collection("items").document(item_id)
        item = item_ref.get()
        if not item.exists:
            raise ValueError("Invalid item_id")

        item_data = item.to_dict()

        # Check if the location_id is valid
        if location_id is not None:
            # Check if the location_id exists
            locations_ref = db.collection("locations")
            query_ref = locations_ref.where(
                filter=FieldFilter(field_path="location_id", op_string="==", value=location_id)
            )
            locations = query_ref.get()
            if len(locations) == 0:
                raise ValueError("Invalid location_id")

        # Check if the coordinates is valid
        if coordinates is not None:
            # Check if the coordinates are in the correct format
            try:
                coordinates_list = list(map(float, coordinates.split(",")))
            except Exception as e:
                raise ValueError("Invalid coordinates (must be comma-separated numbers)")

            # Check if the coordinates is valid (should be 2 for OUTDOOR location , 3 for INDOOR location)
            locations_ref = db.collection("locations")

            # Get the location for the item
            location_id_for_item = item_data["location_id"]
            query_ref = locations_ref.where(
                filter=FieldFilter(field_path="location_id", op_string="==", value=location_id_for_item)
            )
            locations = query_ref.get()
            location = locations[0].to_dict()

            # Check if the location is INDOOR or OUTDOOR
            if location["type"] == "INDOOR":
                if len(coordinates_list) != 3:
                    raise ValueError("Invalid coordinates (should be 3 for INDOOR location)")
            elif location["type"] == "OUTDOOR":
                if len(coordinates_list) != 2:
                    raise ValueError("Invalid coordinates (should be 2 for OUTDOOR location)")
            else:
                raise ValueError("Invalid location type")

        # Check if the tags is valid
        if tags is not None:
            # Check if the tags is valid (should be comma-separated)
            tags_list = tags.split(",")
            if len(tags_list) == 0:
                raise ValueError("Invalid tags")

            # Check if the tags exist
            tags_ref = db.collection("tags")
            for tag in tags_list:
                query_ref = tags_ref.where(filter=FieldFilter(field_path="tag", op_string="==", value=tag))
                found_tags = query_ref.get()
                if len(found_tags) == 0:
                    raise ValueError(f"Invalid tag: {tag}")

        # Check if the attributes is valid
        if attributes is not None:
            # Check if the attributes are in the correct format
            try:
                new_attributes = dict(attribute.split("=") for attribute in attributes.split(","))
            except Exception as e:
                raise ValueError("Invalid attributes (must be comma-separated key-value pairs)")

            # Check if keys and values are valid (can't contain commas, spaces, or equal signs)
            for key, value in new_attributes.items():
                if "," in key or " " in key or "=" in key:
                    raise ValueError(f"Invalid attribute key (can't contain commas, spaces, or equal signs): {key}")
                if "," in value or " " in value or "=" in value:
                    raise ValueError(
                        f"Invalid attribute value (can't contain commas, spaces, or equal signs): {value}"
                    )

                # Convert the value to an integer or a float if the value is a number
                if is_numeric_string(value):
                    value = convert_to_number(value)

                    # Update the value in the attributes dictionary
                    new_attributes[key] = value

            # Create a new dictionary to hold the updated attributes
            updated_attributes = {}

            # Check if incrementing/decrementing is requested by checking if the key is postfixed with + or -
            for key, value in new_attributes.items():
                if key[-1] == "+" or key[-1] == "-":
                    # Check if the value is a number
                    if not isinstance(value, (int, float)):
                        raise ValueError(f"Invalid attribute value (must be a number to increment/decrement): {value}")

                    # Check if the attribute exists
                    if key[:-1] not in item_data["attributes"]:
                        raise ValueError(f"Invalid attribute key (attribute doesn't exist): {key[:-1]}")

                    # Get the current value of the attribute
                    current_value = item_data["attributes"][key[:-1]]

                    # Check if the current value is a number
                    if not isinstance(current_value, (int, float)):
                        raise ValueError(
                            f"Invalid attribute value (must be a number to increment/decrement): {current_value}"
                        )

                    # Increment/decrement the attribute
                    # Note: The type of the current value (int or float) preserved
                    if key[-1] == "+":
                        if isinstance(current_value, int):
                            updated_attributes[key[:-1]] = current_value + int(value)
                        else:
                            updated_attributes[key[:-1]] = current_value + float(value)
                    else:
                        if isinstance(current_value, int):
                            updated_attributes[key[:-1]] = current_value - int(value)
                        else:
                            updated_attributes[key[:-1]] = current_value - float(value)

                else:
                    # Add the attribute to the updated_attributes dictionary
                    updated_attributes[key] = value

            # Update a sub-item of the attributes parameter of the item document in Firestore
            for key, value in updated_attributes.items():
                item_ref.update({f"attributes.{key}": value})

        # Update a parameter or parameters of the item document in Firestore
        if owner is not None:
            item_ref.update({"owner": owner})
        if name is not None:
            item_ref.update({"name": name})
        if type is not None:
            item_ref.update({"type": type})
        if location_id is not None:
            item_ref.update({"location_id": location_id})
        if coordinates is not None:
            item_ref.update({"coordinates": coordinates_list})
        if tags is not None:
            item_ref.update({"tags": tags})

        # Get the updated item
        updated_item = item_ref.get()

        return updated_item

    # Update the item document in Firestore
    try:
        updated_item = update_transaction(transaction)
    except ValueError as e:
        return str(e), 400

    # Return the item details in CSV format
    return item_to_csv(updated_item), 200


@app.route("/get_item", methods=["GET"])
@handle_firestore_errors
def get_item():
    """
    Returns the details of a specific item.

    Parameters

    - item_id (string): The id of the item.
    - api_key (string): The API key for the user (should be API_KEY_DESIGNER or API_KEY_PLAYER).

    Response

    - item_details (string): The details of the item in CSV format (item_id, name quoted with double quotations, owner, type, coordinates, attributes). If the item has no attributes, the attributes field will be "null".
    - status code (integer): HTTP status code.
    """
    # Extract parameters from the request
    item_id = request.args.get("item_id")
    api_key = request.args.get("api_key")

    # Check if the API key is valid
    if api_key not in [API_KEY_DESIGNER, API_KEY_PLAYER]:
        return "Invalid API key", 400

    # Check if the item_id is valid
    if item_id is None:
        return "Invalid item_id (must be specified)", 400
    else:
        item_ref = db.collection("items").document(item_id)
        item = item_ref.get(retry=custom_retry)
        if item.exists is False:
            return "Invalid item_id (item does not exist)", 400

    # Return the item details in CSV format
    return item_to_csv(item), 200


def calculate_distance_for_outdoor(lat1, lon1, lat2, lon2):
    """
    INTERNAL_FUNCTION

    Calculates the distance in meters between two sets of (lat, lon) coordinates.
    """
    radius = 6371000  # Earth's radius in meters
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = radius * c
    return distance


def calculate_distance_for_indoor(x1, y1, z1, x2, y2, z2):
    """
    INTERNAL_FUNCTION

    Calculates the distance in meters between two sets of (x, y, z) coordinates.
    """
    distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)
    return distance


@app.route("/list_items", methods=["GET"])
@handle_firestore_errors
def list_items():
    """
    Returns a list of all or filtered items within a location specified by its location_id.

    Parameters

    - location_id (string): The location_id for the items.
    - tags (string): A list of tags to filter the items by (default is no filter, optional).
    - max_items (integer): The maximum number of items to return (default is 100).
    - position (float): The position within the location to filter items by. For INDOOR locations, x,y,z coordinates are required. For OUTDOOR locations, latitude and longitude are required.
    - radius (float): The radius from the point within which to filter the items (optional).
    - api_key (string): The API key for the user (should be either API_KEY_DESIGNER or API_KEY_PLAYER).

    Response

    - items (string): A list of items in the specified location in CSV format (item_id, name quoted with double quotations, owner, type, coordinates, attributes). If an item has no attributes, the attributes field will be "null".
    - status code (integer): HTTP status code.

    Notes

    - Since the length of the coordinates is variable (i.e., 3 for INDOOR locations and 2 for OUTDOOR locations), add 0 for OUTDOOR locations' third coordinate.
    - Clients should treat the attributes as a variable-length list.
    """
    # Extract parameters from the request
    location_id = request.args.get("location_id")
    tags = request.args.get("tags")
    max_items = request.args.get("max_items")
    position = request.args.get("position")
    radius = request.args.get("radius")
    api_key = request.args.get("api_key")

    # Check if the API key is valid
    if api_key not in [API_KEY_DESIGNER, API_KEY_PLAYER]:
        return "Invalid API key", 400

    # Check the location_id
    if location_id is None:
        return "location_id is required", 400

    # Check if the location_id is valid
    locations_ref = db.collection("locations")
    query_ref = locations_ref.where(filter=FieldFilter(field_path="location_id", op_string="==", value=location_id))
    locations = query_ref.get(retry=custom_retry)
    if len(locations) == 0:
        return "Invalid location_id", 400

    # Check if the max_items is valid
    if max_items is None:
        max_items = 100
    else:
        max_items = int(max_items)

    # Check if the tags are valid
    if tags is None:
        tags = []
    else:
        tags = tags.split(",")
        # Check all tags are valid
        for tag in tags:
            tags_ref = db.collection("tags")
            query_ref = tags_ref.where(filter=FieldFilter(field_path="name", op_string="==", value=tag))
            found_tags = query_ref.get()
            if len(found_tags) == 0:
                return f"Invalid tag: {tag}", 400

    # Retrieve items for the location_id filtered by tags
    items_ref = db.collection("items")
    query_ref = items_ref.where(filter=FieldFilter(field_path="location_id", op_string="==", value=location_id))

    # If a tag or tags are specified, filter the items by tags
    if len(tags) > 0:
        # Adds a where filter for each tag, resulting in a logical AND across all the tags
        for tag in tags:
            query_ref = query_ref.where(filter=FieldFilter(field_path="tags", op_string="array_contains", value=tag))

    query_ref = query_ref.limit(max_items)
    items = query_ref.get(retry=custom_retry)

    # If the point is specified, filter the items by distance
    if position is not None:
        # Check if the radius is valid (should be a number and greater than 0)
        if radius is None:
            return "radius is required", 400
        else:
            try:
                radius = float(radius)
            except ValueError:
                return "radius should be a number", 400

            if radius <= 0:
                return "radius should be greater than 0", 400

        # Convert the point to a list of floats
        position = position.split(",")
        position = [float(p) for p in position]

        # If the location is INDOOR, filter the items by distance
        if locations[0].to_dict()["type"] == "INDOOR":
            # Check if the length of the position is valid
            if len(position) != 3:
                return "Invalid position (should be x,y,z)", 400

            # Check if the radius is valid
            if radius is None:
                return "radius is required", 400

            # Filter the items by distance
            items = [
                item
                for item in items
                if calculate_distance_for_indoor(
                    position[0],
                    position[1],
                    position[2],
                    item.to_dict()["coordinates"][0],
                    item.to_dict()["coordinates"][1],
                    item.to_dict()["coordinates"][2],
                )
                <= radius
            ]

        # If the location is OUTDOOR, filter the items by distance
        elif locations[0].to_dict()["type"] == "OUTDOOR":
            # Check if the length of the position is valid
            if len(position) != 2:
                return "Invalid position (should be latitude,longitude)", 400

            # Filter the items by distance
            items = [
                item
                for item in items
                if calculate_distance_for_outdoor(
                    position[0], position[1], item.to_dict()["coordinates"][0], item.to_dict()["coordinates"][1]
                )
                <= radius
            ]

    # Convert the items to CSV format. Regarding the coordinates, add trailing 0 if the length is 2 (i.e., OUTDOOR location)
    items_in_csv = ""
    for item in items:
        items_in_csv += item_to_csv(item)

    # Return the items in CSV format
    return items_in_csv, 200


@app.route("/acquire_item", methods=["GET"])
@handle_firestore_errors
def acquire_item():
    """
    Allows a player to acquire an item from a specific location. After acquiring the item, the owner of the item will be changed to A_PLAYER and not visible to other players.

    Parameters

    - item_id (string): The id of the item.
    - api_key (string): The API key for the user (should be API_KEY_PLAYER).

    Response

    - message (string): A message indicating that the item was acquired successfully.
    - status code (integer): HTTP status code.
    """
    # Extract parameters from the request
    item_id = request.args.get("item_id")
    api_key = request.args.get("api_key")

    # Check if the API key is valid
    if api_key != API_KEY_PLAYER:
        return "Invalid API key", 400

    # Change the owner of the item to A_PLAYER
    doc_ref = db.collection("items").document(item_id)
    doc_ref.update(
        {
            "owner": "A_PLAYER",
        },
        retry=custom_retry,
    )

    return "Item acquired successfully", 200


@app.route("/create_location", methods=["GET"])
@handle_firestore_errors
def create_location():
    """
    Allows a designer to create a new location.

    Parameters

    - name (string): The name of the new location (should be unique, can't contain commas).
    - type (string): The type of the new location (should be OUTDOOR or INDOOR).
    - api_key (string): The API key for the user (should be API_KEY_DESIGNER).

    Response

    - message (string): A message (followed by a comma and the unique id of the new location if the location was created successfully).
    - status code (integer): HTTP status code.
    """
    # Extract parameters from the request
    name = request.args.get("name")
    type = request.args.get("type")
    api_key = request.args.get("api_key")

    # Check if the API key is valid
    if api_key != API_KEY_DESIGNER:
        return "Invalid API key", 401

    # Check if the location type is valid
    if type != "OUTDOOR" and type != "INDOOR":
        return "Invalid location type", 400

    # Check if the name is valid (can't contain commas)
    if "," in name:
        return "Invalid location name (can't contain commas)", 400
    elif len(name) == 0:
        return "Invalid location name (can't be empty)", 400

    # Check if the name is already taken
    docs = (
        db.collection("locations")
        .where(filter=FieldFilter(field_path="name", op_string="==", value=name))
        .get(retry=custom_retry)
    )
    if len(docs) > 0:
        return "Name already taken", 400

    # Generate a unique id for the location
    location_id = str(uuid.uuid4())

    # Create a new location document in Firestore
    doc_ref = db.collection("locations").document(location_id)
    doc_ref.set(
        {
            "location_id": location_id,
            "name": name,
            "type": type,
        },
        retry=custom_retry,
    )

    return f"Location created successfully,{location_id}", 200


@app.route("/delete_location", methods=["GET"])
@handle_firestore_errors
def delete_location():
    """
    Allows a designer to delete a location.

    Parameters

    - location_id (string): The id of the location.
    - api_key (string): The API key for the user (should be API_KEY_DESIGNER).

    Response

    - message (string): A message indicating that the location was deleted successfully.
    - status code (integer): HTTP status code.
    """
    # Extract parameters from the request
    api_key = request.args.get("api_key")
    location_id = request.args.get("location_id")

    # Check if the API key is valid
    if api_key != API_KEY_DESIGNER:
        return "Invalid API key", 401

    # Check if the location exists
    doc_ref = db.collection("locations").document(location_id)
    location = doc_ref.get(retry=custom_retry)
    if not location.exists:
        return "Location does not exist", 400

    # Delete the location document from Firestore
    doc_ref.delete(retry=custom_retry)

    # Delete the items in the location from Firestore
    docs = (
        db.collection("items")
        .where(filter=FieldFilter(field_path="location_id", op_string="==", value=location_id))
        .get(retry=custom_retry)
    )
    for doc in docs:
        doc.reference.delete(retry=custom_retry)

    return "Location deleted successfully", 200


@app.route("/list_locations", methods=["GET"])
@handle_firestore_errors
def list_locations():
    """
    Returns a list of all locations.

    Parameters

    - api_key (string): The API key for the user (should be API_KEY_DESIGNER).

    Response

    - locations (string): A list of locations in CSV format (id, name quoted with double quotations, type).
    - status code (integer): HTTP status code.
    """
    # Extract parameters from the request
    api_key = request.args.get("api_key")

    # Get the location documents from Firestore
    docs = db.collection("locations").get(retry=custom_retry)

    # Create a list of locations
    locations = []
    for doc in docs:
        location = doc.to_dict()
        location["id"] = doc.id
        locations.append(location)

    # If there are no locations, return "NO_LOCATIONS"
    if len(locations) == 0:
        return "NO_LOCATIONS", 200

    # Convert the locations to CSV format
    locations_csv = ""
    for location in locations:
        name_str = f'"{location["name"]}"'
        locations_csv += f"{location['id']},{name_str},{location['type']}\n"

    return locations_csv, 200


@app.route("/create_tag", methods=["GET"])
@handle_firestore_errors
def create_tag():
    """
    Creates a new and unique tag.

    Parameters

    - name (string): The name of the tag (should be unique, can't contain spaces or commas).
    - api_key (string): The API key for the user (should be API_KEY_DESIGNER).

    Response

    - message (string): A message indicating that the tag was created successfully.
    - status code (integer): HTTP status code.
    """
    # Extract parameters from the request
    name = request.args.get("name")
    api_key = request.args.get("api_key")

    # Check if the API key is valid
    if api_key != API_KEY_DESIGNER:
        return "Invalid API key", 400

    # Check if the name is valid
    if name is None:
        return "name is required", 400
    if " " in name:
        return "name can't contain spaces", 400
    if "," in name:
        return "name can't contain commas", 400

    # Check if the name is unique
    tags_ref = db.collection("tags")
    query_ref = tags_ref.where(filter=FieldFilter("name", "==", name))
    tags = query_ref.get(retry=custom_retry)
    if len(tags) > 0:
        return "name must be unique", 400

    # Generate a unique id for the tag
    tag_id = str(uuid.uuid4())

    # Create a new tag document in Firestore
    doc_ref = db.collection("tags").document(tag_id)
    doc_ref.set({"tag_id": tag_id, "name": name}, retry=custom_retry)

    # Return a message telling that the tag was created successfully
    return f"Tag created successfully,{tag_id}", 200


@app.route("/list_tags", methods=["GET"])
@handle_firestore_errors
def list_tags():
    """
    Returns a list of all tags.

    Parameters

    - max_tags (integer): The maximum number of tags to return (default is 100).
    - api_key (string): The API key for the user (should be API_KEY_DESIGNER).

    Response

    - tags (string): A list of tags in CSV format (name).
    - status code (integer): HTTP status code.
    """
    # Extract parameters from the request
    max_tags = request.args.get("max_tags")
    api_key = request.args.get("api_key")

    # Check if the API key is valid
    if api_key != API_KEY_DESIGNER:
        return "invalid API key", 400

    # Check if the max_tags is valid
    if max_tags is None:
        max_tags = 100
    else:
        max_tags = int(max_tags)

    # Get the tags from Firestore
    tags_ref = db.collection("tags")
    query_ref = tags_ref.order_by("name").limit(max_tags)
    tags = query_ref.get(retry=custom_retry)

    # If there are no tags, return "NO_TAGS"
    if len(tags) == 0:
        return "NO_TAGS", 200

    # Return the tags in CSV format
    tags_csv = ""

    # Convert the tags to CSV format
    for tag in tags:
        tags_csv += f"{tag.to_dict()['name']},"

    # Remove the last comma
    tags_csv = tags_csv[:-1]

    return tags_csv, 200


@app.route("/delete_tag", methods=["GET"])
@handle_firestore_errors
def delete_tag():
    """
    Allows a designer to delete a tag.

    Parameters

    - tag (string): The name of the tag.
    - api_key (string): The API key for the user (should be API_KEY_DESIGNER).

    Response

    - message (string): A message indicating that the tag was deleted successfully.
    - status code (integer): HTTP status code.
    """
    # Extract parameters from the request
    tag = request.args.get("tag")
    api_key = request.args.get("api_key")

    # Check if the API key is valid
    if api_key != API_KEY_DESIGNER:
        return "Invalid API key", 400

    # Check if the tag is valid
    if tag is None:
        return "tag is required", 400

    # Check if the tag exists
    tags_ref = db.collection("tags")
    query_ref = tags_ref.where(filter=FieldFilter("name", "==", tag))
    tags = query_ref.get(retry=custom_retry)
    if len(tags) == 0:
        return "The tag does not exist", 400

    # Delete the tag document from Firestore
    doc_ref = db.collection("tags").document(tags[0].id)
    doc_ref.delete(retry=custom_retry)

    # Return a message telling that the tag was deleted successfully
    return "The tag was deleted successfully", 200


@app.route("/update_attribute", methods=["GET"])
@handle_firestore_errors
def update_attribute():
    """
    Allows a player or a sensor to update an attribute of an item.

    Parameters

    - item_id (string): The id of the item.
    - attribute (string): The attribute of the item in key-value format (e.g., "temperature=20"). You can increment/decrement an attribute by using the following format: "votes=+1" or "votes=-1".
    - api_key (string): The API key for the user (should be API_KEY_DESIGNER or API_KEY_PLAYER or API_KEY_SENSOR).

    Response

    - message (string): The updated attribute value.
    - status code (integer): HTTP status code.
    """
    # Extract parameters from the request
    item_id = request.args.get("item_id")
    attribute = request.args.get("attribute")
    api_key = request.args.get("api_key")

    # Check if the API key is valid
    if api_key not in [API_KEY_DESIGNER, API_KEY_PLAYER, API_KEY_SENSOR]:
        return "Invalid API key (should be API_KEY_DESIGNER or API_KEY_PLAYER or API_KEY_SENSOR)", 400

    # Check if the item_id is valid
    if item_id == None or item_id == "":
        return "Invalid item_id", 400

    # Check if the attribute is valid
    if attribute == None or attribute == "":
        return "Invalid attribute (should be in key-value format, e.g., 'temperature=20')", 400

    # Split the attribute into key and value
    key_value = attribute.split("=")
    if len(key_value) != 2:
        return "Invalid attribute (should be in key-value format, e.g., 'temperature=20')", 400

    # Create a transaction
    transaction = db.transaction()

    # Use a transaction to update the attribute of the item document in Firestore
    @firestore.transactional
    def update_transaction(transaction):
        key = key_value[0]
        value = key_value[1]

        doc_ref = db.collection("items").document(item_id)
        item = doc_ref.get(retry=custom_retry)
        if item.exists == False:
            raise ValueError("Invalid item_id")

        # Convert the value to an integer or a float if the value is a number
        if is_numeric_string(value):
            value = convert_to_number(value)

        # Check if increment/decrement postfix is used in the key
        if key[-1] == "+" or key[-1] == "-":
            # Check if the value is int or float
            if not isinstance(value, (int, float)):
                raise ValueError("Invalid attribute (value should be a number to increment/decrement)")

            # Get the current value of the attribute
            current_value = item.to_dict()["attributes"][key[:-1]]

            # Check if the current value is a number
            if current_value is None or not isinstance(current_value, (int, float)):
                raise ValueError("Invalid attribute (current value should be a number to increment/decrement)")

            # Increment/decrement the value
            # Note: The type of the value preserved (int or float)
            if key[-1] == "+":
                if isinstance(current_value, int):
                    value = current_value + int(value)
                else:
                    value = current_value + float(value)
            else:
                if isinstance(current_value, int):
                    value = current_value - int(value)
                else:
                    value = current_value - float(value)

            # Remove the postfix from the key
            key = key[:-1]

        # Update the attribute of the item document in Firestore
        transaction.update(doc_ref, {f"attributes.{key}": value})

        # Return the updated attribute value
        return str(value)

    # Update the attribute of the item document in Firestore
    try:
        updated_value = update_transaction(transaction)
    except ValueError as e:
        return str(e), 400

    # Return the updated attribute value
    return updated_value, 200


@app.route("/get_attribute", methods=["GET"])
@handle_firestore_errors
def get_attribute():
    """
    Allows a player or an actuator to read an attribute of an item.

    Parameters

    - item_id (string): The id of the item.
    - attribute (string): The attribute of the item.
    - api_key (string): The API key for the user (should be API_KEY_DESIGNER or API_KEY_PLAYER or API_KEY_ACTUATOR).

    Response

    - item_status (string): The value of the attribute.
    - status code (integer): HTTP status code.
    """
    # Extract parameters from the request
    item_id = request.args.get("item_id")
    attribute = request.args.get("attribute")
    api_key = request.args.get("api_key")

    # Check if the API key is valid
    if api_key not in [API_KEY_DESIGNER, API_KEY_PLAYER, API_KEY_ACTUATOR]:
        return "Invalid API key (should be API_KEY_DESIGNER or API_KEY_PLAYER or API_KEY_ACTUATOR)", 400

    # Check if the item_id is valid
    if item_id == None or item_id == "":
        return "Invalid item_id", 400

    # Get the item document from Firestore
    doc_ref = db.collection("items").document(item_id)
    item = doc_ref.get(retry=custom_retry)

    # Check if the item exists
    if not item.exists:
        return "Invalid item_id", 400

    # Check if the attribute name is valid
    if attribute not in item.to_dict()["attributes"]:
        return "Invalid attribute (attribute does not exist)", 400

    # Return the value of the attribute
    return str(item.to_dict()["attributes"][attribute]), 200


if __name__ == "__main__":
    app.run(debug=True)
