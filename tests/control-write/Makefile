TOP=		../..
include ${TOP}/iconfig.mk

PROG=		control-write-test
CFLAGS?=	-O2
CSTD?=		c99
CFLAGS+=	-std=${CSTD}
CPPFLAGS+=	-I${TOP} -I${TOP}/src

all: ${PROG}

${PROG}: control-write-test.c ${TOP}/src/control-write.c
	${CC} ${CFLAGS} ${CPPFLAGS} ${LDFLAGS} -o $@ \
	    control-write-test.c ${TOP}/src/control-write.c

test: ${PROG}
	./${PROG}

clean:
	rm -f ${PROG} ${PROG}.core

distclean: clean
