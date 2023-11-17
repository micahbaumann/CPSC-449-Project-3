# Name of the virtual environment
VENV_NAME?=.venv

# Activate the virtual environment
VENV_ACTIVATE=$(VENV_NAME)/bin/activate

# Python and pip inside the virtual environment
PYTHON=$(VENV_NAME)/bin/python3
PIP=$(VENV_NAME)/bin/pip3

all: venv

# Create the virtual environment
create-venv:
	@test -d $(VENV_NAME) || python3 -m venv $(VENV_NAME)

venv: create-venv $(VENV_ACTIVATE)

venv: create-venv
	@$(PIP) install -U pip
	@$(PIP) install -r requirements.txt

clean:
	@rm -rf $(VENV_NAME)

.PHONY: all create-venv venv clean