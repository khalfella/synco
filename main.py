#!/usr/bin/python3 -u

import mailbox
import os
import stat
import time

from email import utils


#
# Constants that is expected to be converted to
# environment variabled later on when this software
# about to be turned to something one can run inside
# a docker container.
#

DIRPATH = '/home/khalfella/synco/fsdir'

MAILBOXPATH = '/home/khalfella/Mail/gmail/Synco'
MAILBOXCREATE = True


SYNCO_MSG_FORMAT_UNICODE_SURROGATE = 'X-Synco-Unicode-Surrogate'
SYNCO_MSG_FILE_TYPE_REG = 'REG'


#
# List of headers that will be stored in email message
#
MSG_FORMAT_HDR    = 'X-Synco-Format'
MSG_FILE_PATH_HDR = 'X-Synco-File-Path'
MSG_FILE_TYPE_HDR = 'X-Synco-File-Type'
MSG_MODE_HDR      = 'X-Synco-Mode'
MSG_MTIME_HDR     = 'X-Synco-MTime'
MSG_UID_HDR       = 'X-Synco-Uid'
MSG_GID_HDR       = 'X-Synco-Gid'

MSG_KEY           = 'X-Synco-Message-Key'

def walk_fdir(dirpath):
    os.chdir(dirpath)
    contents = {}
    for root, dirs, files in os.walk("."):
        for filename in files:
            filepath = os.path.join(root, filename)
            st = os.lstat(filepath)
            mode = st.st_mode
            if not stat.S_ISREG(mode):
                continue

            contents[filepath] = {
                MSG_FILE_PATH_HDR: filepath,
                MSG_MTIME_HDR: st.st_mtime,
            }

    return contents


def walk_mdir(mdir):
    contents = {}
    for key in mdir.keys():
        msg = mdir[key]
        msg_format = msg[MSG_FORMAT_HDR]
        if msg_format != SYNCO_MSG_FORMAT_UNICODE_SURROGATE:
            continue

        filepath = msg[MSG_FILE_PATH_HDR]
        mtime = float(msg[MSG_MTIME_HDR])

        if filepath in contents:
            emtime = contents[filepath][MSG_MTIME_HDR]
            if emtime >= mtime:
                continue

        contents[filepath] = {
            MSG_KEY: key,
            MSG_FILE_PATH_HDR: filepath,
            MSG_MTIME_HDR: mtime,
            MSG_FILE_TYPE_HDR: msg[MSG_FILE_TYPE_HDR],
            MSG_MODE_HDR: int(msg[MSG_MODE_HDR]),
            MSG_UID_HDR: int(msg[MSG_UID_HDR]),
            MSG_GID_HDR: int(msg[MSG_GID_HDR]),
        }

    return contents


def sync_fdir_to_mdir(files, fdir, mdir):
    for filename in files:
        filepath = os.path.join(fdir, filename)

        st = os.lstat(filepath)
        mode = st.st_mode
        if not stat.S_ISREG(mode):
            continue

        msg = mailbox.MaildirMessage()
        msg[MSG_FORMAT_HDR] = SYNCO_MSG_FORMAT_UNICODE_SURROGATE
        msg[MSG_FILE_PATH_HDR] = filename
        msg[MSG_FILE_TYPE_HDR] = SYNCO_MSG_FILE_TYPE_REG
        msg[MSG_MODE_HDR] = str(stat.S_IMODE(mode))
        msg[MSG_MTIME_HDR] = str(st.st_mtime)
        msg[MSG_UID_HDR] = str(st.st_uid)
        msg[MSG_GID_HDR] = str(st.st_gid)

        msg['Subject'] = filename
        msg['Date'] = utils.formatdate(st.st_mtime)
        msg.set_type('text/plain')
        msg.set_date(st.st_mtime)
        msg.set_subdir('cur')


        with open(filepath, 'rb') as f:
            data = f.read()
            data = data.decode(encoding="ascii", errors="surrogateescape")
            msg.set_payload(data)

        mdir.add(msg)
    mdir.flush()


def sync_mdir_to_fdir(files, fdir, mdir, mdir_contents):
    for filename in files:
        filepath = os.path.join(fdir, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        msg_entry = mdir_contents[filename]

        with open(filepath, 'wb') as f:
            msg_key = msg_entry[MSG_KEY]
            data = mdir[msg_key].get_payload()
            data = data.encode(errors="surrogateescape")
            f.write(data)
            f.flush()

        os.utime(filepath, (msg_entry[MSG_MTIME_HDR], msg_entry[MSG_MTIME_HDR]))
        os.chown(filepath, msg_entry[MSG_UID_HDR], msg_entry[MSG_GID_HDR])


def walk_common(files, fdir_contents, mdir_contents):
    fdir_to_mdir = set()
    mdir_to_fdir = set()
    for filename in files:
        fentry_mtime = fdir_contents[filename][MSG_MTIME_HDR]
        mentry_mtime = mdir_contents[filename][MSG_MTIME_HDR]
        if mentry_mtime > fentry_mtime:
            mdir_to_fdir.add(filename)
        elif fentry_mtime > mentry_mtime:
            fdir_to_mdir.add(filename)
    return fdir_to_mdir, mdir_to_fdir

def main():
    fdir = DIRPATH
    mdir = mailbox.Maildir(MAILBOXPATH, create=MAILBOXCREATE)

    fdir_contents = walk_fdir(DIRPATH)
    mdir_contents = walk_mdir(mdir)

    print(fdir_contents)
    print(mdir_contents)

    fdir_filepaths = set(fdir_contents.keys())
    mdir_filepaths = set(mdir_contents.keys())

    fdir_to_mdir = fdir_filepaths - mdir_filepaths
    mdir_to_fdir = mdir_filepaths - fdir_filepaths

    print(f"fdir_to_mdir = {fdir_to_mdir}")
    print(f"mdir_to_fdir = {mdir_to_fdir}")

    sync_fdir_to_mdir(fdir_to_mdir, fdir, mdir)
    sync_mdir_to_fdir(mdir_to_fdir, fdir, mdir, mdir_contents)

    # Handle common files based on mtime
    common = fdir_filepaths.intersection(mdir_filepaths)
    fdir_to_mdir, mdir_to_fdir = walk_common(common, fdir_contents, mdir_contents)

    print(f"fdir_to_mdir_common = {fdir_to_mdir}")
    print(f"mdir_to_fdir_common = {mdir_to_fdir}")

    sync_fdir_to_mdir(fdir_to_mdir, fdir, mdir)
    sync_mdir_to_fdir(mdir_to_fdir, fdir, mdir, mdir_contents)

if __name__ == '__main__':
    main()
