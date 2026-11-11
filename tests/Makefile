SUBDIRS=	crypt eloop-bench

.PHONY:	test-listen-fd

test-listen-fd:
	@test -n "${INTERFACE}" || { echo "INTERFACE must be set"; exit 1; }
	DHCPCD_LISTEN_FD_TEST=1 python3 listen-fd.py ../src/dhcpcd ${INTERFACE}

all: 
	for x in ${SUBDIRS}; do cd $$x; ${MAKE} $@ || exit $$?; cd ..; done

install:

proginstall:

clean:
	for x in ${SUBDIRS}; do cd $$x; ${MAKE} $@ || exit $$?; cd ..; done

distclean: clean
	rm -f *.diff *.patch *.orig *.rej
	for x in ${SUBDIRS}; do cd $$x; ${MAKE} $@ || exit $$?; cd ..; done

test:
	for x in ${SUBDIRS}; do cd $$x; ${MAKE} $@ || exit $$?; cd ..; done

tests: test
