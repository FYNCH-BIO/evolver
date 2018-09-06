.PHONY: test

init:
	pip install --quiet --requirement=requirements.txt
	pip install --quiet --requirement=test-requirements.txt

test:
	flake8 --ignore=E501 --exclude=dpu/socketIO_client dpu
