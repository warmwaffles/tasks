all: build

install:
	cp ./tasks ${HOME}/bin/tasks
	cp ./tasks-add ${HOME}/bin/tasks-add
	cp ./tasks-archive ${HOME}/bin/tasks-archive
	cp ./tasks-clean ${HOME}/bin/tasks-clean
	cp ./tasks-complete ${HOME}/bin/tasks-complete
	cp ./tasks-edit ${HOME}/bin/tasks-edit
	cp ./tasks-init ${HOME}/bin/tasks-init
	cp ./tasks-list ${HOME}/bin/tasks-list
	cp ./tasks-remove ${HOME}/bin/tasks-remove
	cp ./tasks-summary ${HOME}/bin/tasks-summary
	cp ./tasks-uncomplete ${HOME}/bin/tasks-uncomplete

.PHONY: install
