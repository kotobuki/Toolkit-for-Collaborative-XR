# API Documentation

## Roles

| Endpoint | Designer | Player | Sensor | Actuator |
| --- | --- | --- | --- | --- |
| /ping |  |  |  |  |
| /create_item | ✔ |  |  |  |
| /delete_item | ✔ |  |  |  |
| /update_item | ✔ |  |  |  |
| /get_item | ✔ | ✔ |  |  |
| /list_items | ✔ | ✔ |  |  |
| /acquire_item |  | ✔ |  |  |
| /delete_items | ✔ |  |  |  |
| /create_location | ✔ |  |  |  |
| /delete_location | ✔ |  |  |  |
| /list_locations | ✔ |  |  |  |
| /create_tag | ✔ |  |  |  |
| /list_tags | ✔ |  |  |  |
| /delete_tag | ✔ |  |  |  |
| /update_attribute | ✔ | ✔ | ✔ |  |
| /get_attribute | ✔ | ✔ |  | ✔ |

## Endpoints

### `/ping`

Allows a user to check if the server is running.

Response

- `status code` (integer): HTTP status code (always 200).

### `/create_item`

Allows a designer to create a new item with specific attributes, including a timer and visibility.

Parameters

- `location_id` (string): The location_id of the item.
- `owner` (string): The name of the owner of the item, should be either `PUBLIC_DOMAIN` or `A_PLAYER` (optional, default is `PUBLIC_DOMAIN`).
- `name` (string): The name of the item (e.g., "flyer", don't have to be unique, can't contain commas).
- `type` (string): The type of the item (e.g., `FLYER`).
- `coordinates` (string): The coordinates of the item (x, y, z for an `INDOOR` location or latitude, longitude for an `OUTDOOR` location, comma-separated).
- `tags` (string): The tags of the item (comma-separated, e.g., "tag1,tag2", optional).
- `attributes` (string): The attributes of the item (comma-separated, e.g., "color=blue,shape=circle", optional).
- `api_key` (string): The API key for the user (should be `API_KEY_DESIGNER`).

Response

- `message` (string): A message indicating that the item was created successfully.
- `status code` (integer): HTTP status code.

### `/delete_item`

Allows a designer to delete an existing item.

Parameters

- `item_id` (string): The id of the item.
- `api_key` (string): The API key for the user (should be `API_KEY_DESIGNER`).

Response

- `message` (string): A message indicating that the item was deleted successfully.
- `status code` (integer): HTTP status code.

### `/update_item`

Allows a designer to update a parameter or parameters of an existing item. At least one parameter must be specified.

Parameters

- `item_id` (string): The id of the item.
- `owner` (string): The name of the owner of the item, should be either `PUBLIC_DOMAIN` or `A_PLAYER` (optional).
- `name` (string): The name of the item (e.g., "flyer", don't have to be unique, optional).
- `type` (string): The type of the item (e.g., `FLYER`, optional).
- `location_id` (string): The location_id of the item (optional).
- `coordinates` (string): The coordinates of the item (x, y, z for an `INDOOR` location or latitude, longitude for an `OUTDOOR` location, comma-separated, optional).
- `tags` (string): The tags of the item (comma-separated, e.g., "tag1,tag2", optional).
- `attributes` (string): The attributes of the item (comma-separated, e.g., "color=blue,shape=circle", optional). You can increment/decrement an attribute by using the following format: "votes=+1" or "votes=-1".
- `api_key` (string): The API key for the user (should be `API_KEY_DESIGNER`).

Response

- `message` (string): A message indicating that the item was updated successfully.
- `status code` (integer): HTTP status code.

### `/get_item`

Returns the details of a specific item.

Parameters

- `item_id` (string): The id of the item.
- `api_key` (string): The API key for the user (should be `API_KEY_DESIGNER` or `API_KEY_PLAYER`).

Response

- `item_details` (string): The details of the item in CSV format (item_id, name quoted with double quotations, owner, type, coordinates, attributes). If the item has no attributes, the attributes field will be "null".
- `status code` (integer): HTTP status code.

### `/list_items`

Returns a list of all or filtered items within a location specified by its location_id.

Parameters

- `location_id` (string): The location_id for the items.
- `tags` (string): A list of tags to filter the items by (default is no filter, optional).
- `max_items` (integer): The maximum number of items to return (default is 100).
- `position` (float): The position within the location to filter items by. For `INDOOR` locations, x,y,z coordinates are required. For `OUTDOOR` locations, latitude and longitude are required.
- `radius` (float): The radius from the point within which to filter the items (optional).
- `api_key` (string): The API key for the user (should be either `API_KEY_DESIGNER` or `API_KEY_PLAYER`).

Response

- `items` (string): A list of items in the specified location in CSV format (item_id, name quoted with double quotations, owner, type, coordinates, attributes). If an item has no attributes, the attributes field will be "null".
- `status code` (integer): HTTP status code.

Notes

- `Since the length of the coordinates is variable` (i.e., 3 for `INDOOR` locations and 2 for `OUTDOOR` locations), add 0 for `OUTDOOR` locations' third coordinate.
- Clients should treat the attributes as a variable-length list.

### `/acquire_item`

Allows a player to acquire an item from a specific location. After acquiring the item, the owner of the item will be changed to `A_PLAYER` and not visible to other players.

Parameters

- `item_id` (string): The id of the item.
- `api_key` (string): The API key for the user (should be `API_KEY_PLAYER`).

Response

- `message` (string): A message indicating that the item was acquired successfully.
- `status code` (integer): HTTP status code.

### `/delete_items`

Allows a designer to delete all items in a location.

Parameters

- `location_id` (string): The id of the location.
- `api_key` (string): The API key for the user (should be `API_KEY_DESIGNER`).

Response

- `message` (string): A message indicating that the items was deleted successfully.
- `status code` (integer): HTTP status code.

### `/create_location`

Allows a designer to create a new location.

Parameters

- `name` (string): The name of the new location (should be unique, can't contain commas).
- `type` (string): The type of the new location (should be `OUTDOOR` or `INDOOR`).
- `api_key` (string): The API key for the user (should be `API_KEY_DESIGNER`).

Response

- `message` (string): A message (followed by a comma and the unique id of the new location if the location was created successfully).
- `status code` (integer): HTTP status code.

### `/delete_location`

Allows a designer to delete a location.

Parameters

- `location_id` (string): The id of the location.
- `api_key` (string): The API key for the user (should be `API_KEY_DESIGNER`).

Response

- `message` (string): A message indicating that the location was deleted successfully.
- `status code` (integer): HTTP status code.

### `/list_locations`

Returns a list of all locations.

Parameters

- `api_key` (string): The API key for the user (should be `API_KEY_DESIGNER`).

Response

- `locations` (string): A list of locations in CSV format (id, name quoted with double quotations, type).
- `status code` (integer): HTTP status code.

### `/create_tag`

Creates a new and unique tag.

Parameters

- `name` (string): The name of the tag (should be unique, can't contain spaces or commas).
- `api_key` (string): The API key for the user (should be `API_KEY_DESIGNER`).

Response

- `message` (string): A message indicating that the tag was created successfully.
- `status code` (integer): HTTP status code.

### `/list_tags`

Returns a list of all tags.

Parameters

- `max_tags` (integer): The maximum number of tags to return (default is 100).
- `api_key` (string): The API key for the user (should be `API_KEY_DESIGNER`).

Response

- `tags` (string): A list of tags in CSV format (name).
- `status code` (integer): HTTP status code.

### `/delete_tag`

Allows a designer to delete a tag.

Parameters

- `tag` (string): The name of the tag.
- `api_key` (string): The API key for the user (should be `API_KEY_DESIGNER`).

Response

- `message` (string): A message indicating that the tag was deleted successfully.
- `status code` (integer): HTTP status code.

### `/update_attribute`

Allows a player or a sensor to update an attribute of an item.

Parameters

- `item_id` (string): The id of the item.
- `attribute` (string): The attribute of the item in key-value format (e.g., "temperature=20"). You can increment/decrement an attribute by using the following format: "votes=+1" or "votes=-1".
- `api_key` (string): The API key for the user (should be `API_KEY_DESIGNER` or `API_KEY_PLAYER` or `API_KEY_SENSOR`).

Response

- `message` (string): The updated attribute value.
- `status code` (integer): HTTP status code.

### `/get_attribute`

Allows a player or an actuator to read an attribute of an item.

Parameters

- `item_id` (string): The id of the item.
- `attribute` (string): The attribute of the item.
- `api_key` (string): The API key for the user (should be `API_KEY_DESIGNER` or `API_KEY_PLAYER` or `API_KEY_ACTUATOR`).

Response

- `item_status` (string): The value of the attribute.
- `status code` (integer): HTTP status code.
