from anaphora import Noun


class app(Noun):
	pass

# NOTE: more complex before/after functionality pending user feedback; trying not to waste development time on functionality for the 1%.

with app("TDVer").grammar(["need", "goal", "requirement"]):
	# ideal if these work, but I'd rather move on for now than get bogged down in how to test the command portion of this.
	# start works properly
	# make a change, test that it triggers the desired check status
	# test that it causes the appropriate update result
	# linters
	with goal("code meets style standards"):
		with requirement("code passes pep8") as pep8:
			pep8.command("pep8 . --ignore=W191,E501")
		with requirement("code passes pylint") as pylint:
			pylint.command("pylint tdver -r n --disable=missing-docstring,")
		with requirement("docs pass pep257") as pep257:
			pep257.command("pep257 .")
