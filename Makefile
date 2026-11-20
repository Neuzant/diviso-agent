.PHONY: test doctor demo
test:
	python -m pytest -q
doctor:
	diviso doctor
demo:
	diviso run --provider mock "Summarise what Diviso is"
