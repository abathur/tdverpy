import json
try:
	with open("tdver.json", "r") as f:
		config = json.load(f)  # pylint: disable=invalid-name
except FileNotFoundError:
	config = {}  # pylint: disable=invalid-name
	# with open("tdver.json", "w") as f:
	# 	json.dump(config, f, sort_keys=True, indent=4)
