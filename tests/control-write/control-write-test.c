/* SPDX-License-Identifier: BSD-2-Clause */
/*
 * dhcpcd - DHCP client daemon
 * Copyright (c) 2026 Drivenets
 * All rights reserved.
 */

#include <sys/uio.h>

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "dhcpcd.h"
#include "control.h"

static char output[1024];
static size_t output_len;
static const ssize_t *write_results;
static size_t write_results_len;
static size_t write_result_index;

ssize_t
writev(int fd, const struct iovec *iov, int iovcnt)
{
	size_t limit, written = 0, n;
	int i;

	(void)fd;
	if (write_result_index >= write_results_len)
		limit = SIZE_MAX;
	else {
		ssize_t result = write_results[write_result_index++];

		if (result < 0) {
			errno = (int)-result;
			return -1;
		}
		limit = (size_t)result;
	}

	for (i = 0; i < iovcnt && written < limit; i++) {
		n = iov[i].iov_len;
		if (n > limit - written)
			n = limit - written;
		if (n > sizeof(output) - output_len)
			return -1;
		memcpy(output + output_len, iov[i].iov_base, n);
		output_len += n;
		written += n;
	}
	return (ssize_t)written;
}

static int
test_partial_write_and_eagain(void)
{
	static char payload[] = "early dhcpcd event";
	static const ssize_t results[] = { 3, -EAGAIN, 7, -EAGAIN, 4, 1024 };
	static const size_t offsets[] = { 3, 3, 10, 10, 14,
	    sizeof(size_t) + sizeof(payload) - 1 };
	static const int completed[] = { 0, 0, 0, 0, 0, 1 };
	struct fd_data data;
	char expected[sizeof(size_t) + sizeof(payload) - 1];
	size_t i;

	memset(&data, 0, sizeof(data));
	data.data = payload;
	data.data_len = sizeof(payload) - 1;
	data.data_flags = FD_SENDLEN;
	memcpy(expected, &data.data_len, sizeof(data.data_len));
	memcpy(expected + sizeof(data.data_len), payload, data.data_len);
	output_len = write_result_index = 0;
	write_results = results;
	write_results_len = sizeof(results) / sizeof(results[0]);

	for (i = 0; i < write_results_len; i++) {
		int result = control_write_data(-1, &data);

		if (result != completed[i] || data.data_offset != offsets[i]) {
			fprintf(stderr, "partial-write step %zu: result %d, offset %zu\n",
			    i, result, data.data_offset);
			return -1;
		}
	}
	if (output_len != sizeof(expected) ||
	    memcmp(output, expected, sizeof(expected)) != 0)
	{
		fprintf(stderr, "partial-write output did not preserve the frame\n");
		return -1;
	}
	return 0;
}

static int
test_disconnect(void)
{
	static char payload[] = "event";
	static const ssize_t results[] = { -EPIPE };
	struct fd_data data;

	memset(&data, 0, sizeof(data));
	data.data = payload;
	data.data_len = sizeof(payload) - 1;
	data.data_flags = FD_SENDLEN;
	output_len = write_result_index = 0;
	write_results = results;
	write_results_len = sizeof(results) / sizeof(results[0]);
	errno = 0;
	if (control_write_data(-1, &data) != -1 || errno != EPIPE) {
		fprintf(stderr, "disconnect was not returned as a fatal write\n");
		return -1;
	}
	return 0;
}

static int
test_unframed_partial_write(void)
{
	static char payload[] = "control response";
	static const ssize_t results[] = { 2, -EAGAIN, 1024 };
	static const size_t offsets[] = { 2, 2, sizeof(payload) - 1 };
	static const int completed[] = { 0, 0, 1 };
	struct fd_data data;
	size_t i;

	memset(&data, 0, sizeof(data));
	data.data = payload;
	data.data_len = sizeof(payload) - 1;
	output_len = write_result_index = 0;
	write_results = results;
	write_results_len = sizeof(results) / sizeof(results[0]);

	for (i = 0; i < write_results_len; i++) {
		int result = control_write_data(-1, &data);

		if (result != completed[i] || data.data_offset != offsets[i]) {
			fprintf(stderr, "unframed-write step %zu: result %d, offset %zu\n",
			    i, result, data.data_offset);
			return -1;
		}
	}
	if (output_len != sizeof(payload) - 1 ||
	    memcmp(output, payload, sizeof(payload) - 1) != 0)
	{
		fprintf(stderr, "unframed write did not preserve the payload\n");
		return -1;
	}
	return 0;
}

int
main(void)
{
	if (test_partial_write_and_eagain() == -1 ||
	    test_disconnect() == -1 ||
	    test_unframed_partial_write() == -1)
		return 1;
	puts("control writer tests passed");
	return 0;
}
