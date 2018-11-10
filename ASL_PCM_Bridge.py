#! /usr/bin/python3

import sys
import multiprocessing as mp
import socket 


def main():

    pipe = mp.Pipe()

    p = mp.Process(target=out, args=(pipe[0], ))
    p.start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 32001))

    while True:
        data = sock.recv(4096)
        if data:
            pipe[1].send_bytes(data)

    p.join()


def out(queue):

    local_buffer = b''

    while True:

        if queue.poll():
            data = queue.recv_bytes()
            local_buffer += b''.join([item[28:] for item in data.split(b'USRP')])
        elif local_buffer:
            #data = data.split(b'USRP')
            #data = b''.join([item[28:] for item in data])
            sys.stdout.buffer.write(local_buffer)
            sys.stdout.flush()
            local_buffer = b''



if __name__ == "__main__":
    main()
