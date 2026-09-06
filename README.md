# dhcpcd

dhcpcd is a
[DHCP](https://en.wikipedia.org/wiki/Dynamic_Host_Configuration_Protocol) and a
[DHCPv6](https://en.wikipedia.org/wiki/DHCPv6) client.
It's also an IPv4LL (aka [ZeroConf](https://en.wikipedia.org/wiki/Zeroconf))
client.
In layperson's terms, dhcpcd runs on your machine and silently configures your
computer to work on the attached networks without trouble and mostly without
configuration.

If you're a desktop user then you may also be interested in
[Network Configurator (dhcpcd-ui)](http://roy.marples.name/projects/dhcpcd-ui)
which sits in the notification area and monitors the state of the network via
dhcpcd.
It also has a nice configuration dialog and the ability to enter a pass phrase
for wireless networks.

dhcpcd may not be the only daemon running that wants to configure DNS on the
host, so it uses [openresolv](http://roy.marples.name/projects/openresolv)
to ensure they can co-exist.

See [BUILDING.md](BUILDING.md) for how to build dhcpcd.

## Configuration

You should read the dhcpcd.conf man page
and put your options into `/etc/dhcpcd.conf`.
The default configuration file should work for most people just fine.
Here it is, in case you lose it.

```
# A sample configuration for dhcpcd.
# See dhcpcd.conf(5) for details.

# Allow users of this group to interact with dhcpcd via the control socket.
#controlgroup wheel

# Inform the DHCP server of our hostname for DDNS.
hostname

# Use the hardware address of the interface for the Client ID.
#clientid
# or
# Use the same DUID + IAID as set in DHCPv6 for DHCPv4 ClientID as per RFC4361.
# Some non-RFC compliant DHCP servers do not reply with this set.
# In this case, comment out duid and enable clientid above.
duid

# Persist interface configuration when dhcpcd exits.
persistent

# Rapid commit support.
# Safe to enable by default because it requires the equivalent option set
# on the server to actually work.
option rapid_commit

# A list of options to request from the DHCP server.
option domain_name_servers, domain_name, domain_search, host_name
option classless_static_routes
# Respect the network MTU. This is applied to DHCP routes.
option interface_mtu

# Most distributions have NTP support.
#option ntp_servers

# A ServerID is required by RFC2131.
require dhcp_server_identifier

# Generate SLAAC address using the Hardware Address of the interface
#slaac hwaddr
# OR generate Stable Private IPv6 Addresses based from the DUID
slaac private
```

The dhcpcd man page has a lot of the same options and more,
which only apply to calling dhcpcd from the command line.


## Compatibility
dhcpcd-5 is only fully command line compatible with dhcpcd-4. 
For compatibility with older versions, use dhcpcd-4.

## Upgrading
dhcpcd-7 defaults the database directory to `/var/db/dhcpcd` instead of
`/var/db` and now stores dhcpcd.duid and dhcpcd.secret in there instead of
in /etc.

dhcpcd-9 defaults the run directory to `/var/run/dhcpcd` instead of
`/var/run` and the prefix of dhcpcd has been removed from the files therein.

## Building a Static .deb Package (Drivenets)

To create a statically-linked .deb package for Drivenets (baseos, interfacehandler, containers):

1. **Configure and build from the repository root:**
   ```bash
   ./configure --libexecdir="/usr/lib/dhcpcd" --enable-static --without-udev CFLAGS="-Os -g"
   make
   ```

2. **Install to package directory from the repository root:**
   ```bash
   VERSION=10.0.6-dn_81498e4e
   PKGDIR="$PWD/src/dhcpcd_${VERSION}-dn_amd64"
   make install DESTDIR="$PKGDIR"
   ```
   Replace `VERSION` with the actual package version. `DESTDIR` should be an
   absolute path: the top-level install enters both `src/` and `hooks/`, and a
   relative `DESTDIR` would be interpreted separately from each subdirectory.
   Running `make install` from `src/` skips `hooks/` entirely and omits
   `/usr/lib/dhcpcd/dhcpcd-run-hooks`.

3. **Add Debian control files:**

   Create a `DEBIAN/` directory inside the package folder with:
   - `control` (required) – package metadata
   - `prerm` (optional) – pre-removal script
   - `postrm` (optional) – post-removal script

4. **Build the .deb:**
   ```bash
   dpkg-deb --build /path/to/dhcpcd_<VERSION>-dn_amd64
   ```

5. **Upload to Minio:**

   Upload the `.deb` file to:
   ```
   http://minioio.dev.drivenets.net:9000/minio/infra-cmc/deb-packages/
   ```

6. **Update package URLs in dependent repos:**

   Update the download URL in the following files:
   - `interface-handler`: `Dockerfile.cheetah-tests`
   - `cheetah`: `image/onie/docker/scripts/deimage.sh`
   - `cheetah`: `containers/ubuntu/Makefile`

The resulting `.deb` contains a fully static `dhcpcd` binary with no external dependencies.


## ChangeLog
We no longer supply a ChangeLog.
However, you're more than welcome to read the
[commit log](https://github.com/NetworkConfiguration/dhcpcd/commits) and
[release announcements](https://github.com/NetworkConfiguration/dhcpcd/releases).
