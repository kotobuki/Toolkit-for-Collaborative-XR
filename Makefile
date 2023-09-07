all: generate_md generate_test_client

generate_md:
	python docstring_to_md.py server.py

generate_test_client:
	python docstring_to_test_client.py server.py
