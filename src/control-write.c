/* SPDX-License-Identifier: BSD-2-Clause */
/*
 * dhcpcd - DHCP client daemon
 * Copyright (c) 2026 Drivenets
 * All rights reserved.
 */

#include <sys/uio.h>

#include <errno.h>
#include <stdint.h>

#include "dhcpcd.h"
#include "control.h"

/* Return 1 when the frame is complete, 0 when it should be retried, or -1
 * for a fatal write error.  data_offset tracks the serialized frame, including
 * the optional length prefix, so a short write never loses framing or payload.
 */
int
control_write_data(int fd, struct fd_data *data)
{
	struct iovec iov[2];
	size_t prefix_len, total_len, offset;
	ssize_t written;
	int iovcnt;

	if (data == NULL || data->data == NULL || data->data_len == 0) {
		errno = EINVAL;
		return -1;
	}
	prefix_len = data->data_flags & FD_SENDLEN ? sizeof(data->data_len) : 0;
	if (data->data_len > SIZE_MAX - prefix_len) {
		errno = EOVERFLOW;
		return -1;
	}
	total_len = prefix_len + data->data_len;
	if (data->data_offset > total_len) {
		errno = EINVAL;
		return -1;
	}
	if (data->data_offset == total_len)
		return 1;

	offset = data->data_offset;
	if (offset < prefix_len) {
		iov[0].iov_base = (char *)&data->data_len + offset;
		iov[0].iov_len = prefix_len - offset;
		iov[1].iov_base = data->data;
		iov[1].iov_len = data->data_len;
		iovcnt = 2;
	} else {
		offset -= prefix_len;
		iov[0].iov_base = (char *)data->data + offset;
		iov[0].iov_len = data->data_len - offset;
		iovcnt = 1;
	}

	written = writev(fd, iov, iovcnt);
	if (written == -1) {
		if (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK)
			return 0;
		return -1;
	}
	if (written == 0) {
		errno = EPIPE;
		return -1;
	}
	if ((size_t)written > total_len - data->data_offset) {
		errno = EIO;
		return -1;
	}
	data->data_offset += (size_t)written;
	return data->data_offset == total_len ? 1 : 0;
}
