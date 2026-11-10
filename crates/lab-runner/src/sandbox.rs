//! All unsafe IPC and seccomp ABI calls for the untrusted forwarding processes.
use crate::{Event, Result, check};
use link::DATAGRAM;
use std::{
    io,
    os::fd::{FromRawFd, OwnedFd, RawFd},
    os::unix::net::UnixDatagram,
    process::{Command, Stdio},
};

pub fn stdio(socket: UnixDatagram) -> Stdio {
    Stdio::from(OwnedFd::from(socket))
}

// SAFETY: The launcher passes exclusive ownership of this inherited socket.
pub fn inherited(fd: RawFd) -> UnixDatagram {
    unsafe { UnixDatagram::from_raw_fd(fd) }
}

#[cfg(all(target_os = "linux", target_arch = "x86_64"))]
fn install() -> io::Result<()> {
    const LOAD_WORD: u16 = 0x20;
    const EQUAL: u16 = 0x15;
    const RETURN: u16 = 0x06;
    const GREATER: u16 = 0x25;
    const AUDIT_ARCH_X86_64: u32 = 0xc000_003e;
    const DENY: u32 = libc::SECCOMP_RET_ERRNO | libc::EPERM as u32;
    let insn = |code, jt, jf, k| libc::sock_filter { code, jt, jf, k };
    let mut code = Vec::with_capacity(64);
    code.extend([
        insn(LOAD_WORD, 0, 0, 4), // audit architecture
        insn(EQUAL, 1, 0, AUDIT_ARCH_X86_64),
        insn(RETURN, 0, 0, libc::SECCOMP_RET_KILL_PROCESS),
        insn(LOAD_WORD, 0, 0, 0), // syscall number, including x32 ABI bit
    ]);
    for syscall in [
        libc::SYS_exit,
        libc::SYS_exit_group,
        libc::SYS_poll,
        libc::SYS_clock_gettime,
        libc::SYS_rt_sigreturn,
    ] {
        code.extend([
            insn(EQUAL, 0, 1, syscall as u32),
            insn(RETURN, 0, 0, libc::SECCOMP_RET_ALLOW),
        ]);
    }
    for syscall in [libc::SYS_sendto, libc::SYS_recvfrom] {
        let checks = [
            insn(LOAD_WORD, 0, 0, 16), // fd, low word
            insn(GREATER, 11, 0, 1),
            insn(LOAD_WORD, 0, 0, 32), // len, low word
            insn(GREATER, 9, 0, (DATAGRAM + 1) as u32),
            insn(LOAD_WORD, 0, 0, 36), // len, high word
            insn(EQUAL, 0, 7, 0),
            insn(LOAD_WORD, 0, 0, 40), // flags (use nonblocking descriptors)
            insn(EQUAL, 0, 5, 0),
            insn(LOAD_WORD, 0, 0, 48), // source/destination pointer
            insn(EQUAL, 0, 3, 0),
            insn(LOAD_WORD, 0, 0, 52),
            insn(EQUAL, 0, 1, 0),
            insn(RETURN, 0, 0, libc::SECCOMP_RET_ALLOW),
            insn(RETURN, 0, 0, DENY),
        ];
        code.push(insn(EQUAL, 0, checks.len() as u8, syscall as u32));
        code.extend(checks);
    }
    code.push(insn(RETURN, 0, 0, DENY));
    let program = libc::sock_fprog {
        len: code.len() as u16,
        filter: code.as_mut_ptr(),
    };
    // SAFETY: BPF is copied by the kernel. Drop all non-IPC descriptors before use.
    unsafe {
        if libc::syscall(libc::SYS_close_range, 2u32, u32::MAX, 0u32) != 0
            || libc::prctl(libc::PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0
            || libc::prctl(libc::PR_SET_SECCOMP, libc::SECCOMP_MODE_FILTER, &program) != 0
        {
            return Err(io::Error::last_os_error());
        }
    }
    Ok(())
}

#[cfg(not(all(target_os = "linux", target_arch = "x86_64")))]
fn install() -> io::Result<()> {
    Err(io::Error::new(
        io::ErrorKind::Unsupported,
        "seccomp policy requires Linux x86-64",
    ))
}

fn denied(result: libc::c_long) -> bool {
    result == -1 && io::Error::last_os_error().raw_os_error() == Some(libc::EPERM)
}

fn restrictions(pid: u32, memory_path: &std::ffi::CStr) -> bool {
    let mut address = libc::sockaddr_in {
        sin_family: libc::AF_INET as u16,
        sin_port: 9u16.to_be(),
        sin_addr: libc::in_addr {
            s_addr: u32::from_ne_bytes([127, 0, 0, 1]),
        },
        sin_zero: [0; 8],
    };
    // SAFETY: The probe pointers remain live for the duration of each syscall.
    unsafe {
        denied(libc::syscall(
            libc::SYS_openat,
            libc::AT_FDCWD,
            c"/etc/passwd".as_ptr(),
            libc::O_RDONLY,
            0,
        )) && denied(libc::syscall(
            libc::SYS_socket,
            libc::AF_INET,
            libc::SOCK_STREAM,
            0,
        )) && denied(libc::syscall(
            libc::SYS_connect,
            0,
            &mut address,
            size_of::<libc::sockaddr_in>(),
        )) && denied(libc::syscall(
            libc::SYS_openat,
            libc::AT_FDCWD,
            memory_path.as_ptr(),
            libc::O_RDONLY,
            0,
        )) && denied(libc::syscall(
            libc::SYS_ptrace,
            libc::PTRACE_ATTACH,
            pid,
            0usize,
            0usize,
        )) && denied(libc::syscall(
            libc::SYS_process_vm_readv,
            pid,
            0usize,
            0usize,
            0usize,
            0usize,
            0usize,
        )) && denied(libc::syscall(libc::SYS_dup, 0))
            && denied(libc::syscall(libc::SYS_sendmsg, 0, 0usize, 0))
            && denied(libc::syscall(libc::SYS_recvmsg, 0, 0usize, 0))
            && denied(libc::syscall(
                libc::SYS_sendto,
                0,
                0usize,
                0usize,
                0,
                &address,
                size_of::<libc::sockaddr_in>(),
            ))
    }
}

fn confine(pid: u32) -> Result<()> {
    let memory_path = std::ffi::CString::new(format!("/proc/{pid}/mem"))?;
    install()?;
    check(
        restrictions(pid, &memory_path),
        "seccomp escape probe failed",
    )
}

fn forward_datagram(fd: RawFd, bytes: &[u8]) -> io::Result<()> {
    // SAFETY: bytes is live, and the connected socket uses no destination address.
    let sent = unsafe {
        libc::sendto(
            fd,
            bytes.as_ptr().cast(),
            bytes.len(),
            0,
            std::ptr::null(),
            0,
        )
    };
    if sent == bytes.len() as isize {
        Ok(())
    } else {
        Err(io::Error::last_os_error())
    }
}

pub fn probe(pid: u32) -> Result<()> {
    confine(pid)?;
    let input = inherited(0);
    let mut packet = [0; DATAGRAM + 1];
    let size = input.recv(&mut packet)?;
    check(size == 6, "isolation probe expected six bytes")?;
    forward_datagram(1, &packet[..size])?;
    Ok(())
}

pub fn forward(mode: &str, pid: u32) -> Result<()> {
    let sockets = [inherited(0), inherited(1)];
    let mut poll = [
        libc::pollfd {
            fd: 0,
            events: libc::POLLIN,
            revents: 0,
        },
        libc::pollfd {
            fd: 1,
            events: libc::POLLIN,
            revents: 0,
        },
    ];
    confine(pid)?;
    let mut scratch = [0; DATAGRAM + 1];
    let mut ready = [false; 2];
    loop {
        // SAFETY: Both entries refer to the inherited datagram sockets.
        if unsafe { libc::poll(poll.as_mut_ptr(), 2, -1) } <= 0 {
            continue;
        }
        for index in 0..2 {
            if poll[index].revents & libc::POLLIN == 0 {
                continue;
            }
            if let Ok(len) = sockets[index].recv(&mut scratch)
                && (link::HEADER..=DATAGRAM).contains(&len)
            {
                if mode == "startup-tamper"
                    && index == 0
                    && len == DATAGRAM
                    && scratch[0] == link::STARTUP_MAGIC
                    && scratch[1] == 0
                    && scratch[4] == 1
                {
                    // This byte is in the encrypted ML-KEM public-key field.
                    scratch[link::HEADER] ^= 1;
                }
                let record_id = u32::from_le_bytes(scratch[..4].try_into()?);
                if record_id == 2 && scratch[4] == 128 && scratch[5] == 3 {
                    ready[index] = true;
                }
                if mode == "faults"
                    && index == 0
                    && ready.iter().all(|&x| x)
                    && record_id >= 3
                    && scratch[5] == 0
                {
                    if record_id.is_multiple_of(19) {
                        continue;
                    }
                    if record_id.is_multiple_of(17) && len > link::HEADER + 10 {
                        scratch[link::HEADER + 10] ^= 0x80;
                    }
                }
                if index == 0
                    && mode == "blocked"
                    && scratch[..4] == 2u32.to_le_bytes()
                    && scratch[4] == 128
                    && scratch[5] == 3
                {
                    // Stop only after the final fragment of Alice's Ready.
                    // Invitation records are also 128 bytes and must not count
                    // toward this deliberately blocked-media scenario.
                    poll[0].events = 0;
                }
                if let Err(error) = forward_datagram(1 - index as RawFd, &scratch[..len])
                    && error.kind() != io::ErrorKind::WouldBlock
                {
                    return Err(error.into());
                }
            }
        }
    }
}

pub fn bounded_pair() -> io::Result<(UnixDatagram, UnixDatagram)> {
    let pair = UnixDatagram::pair()?;
    for socket in [&pair.0, &pair.1] {
        use std::os::fd::AsRawFd;
        let bytes: libc::c_int = 8192;
        // SAFETY: The option pointer and length describe a live integer.
        if unsafe {
            libc::setsockopt(
                socket.as_raw_fd(),
                libc::SOL_SOCKET,
                libc::SO_SNDBUF,
                (&raw const bytes).cast(),
                size_of_val(&bytes) as libc::socklen_t,
            )
        } != 0
        {
            return Err(io::Error::last_os_error());
        }
        socket.set_nonblocking(true)?;
    }
    Ok(pair)
}

pub fn test() -> Result<()> {
    let executable = std::env::current_exe()?;
    let mut children = crate::wall::Children::default();
    let (a, _peer) = bounded_pair()?;
    let (parent, control) = UnixDatagram::pair()?;
    parent.set_read_timeout(Some(std::time::Duration::from_secs(5)))?;
    let endpoint = children.add(
        Command::new(&executable)
            .args(["endpoint", ".", "alice", "demo"])
            .stdin(stdio(a))
            .stdout(stdio(control))
            .spawn()?,
    );
    let mut public = [0; protocol::CONTACT];
    check(
        parent.recv(&mut public)? == public.len(),
        "endpoint probe did not start",
    )?;
    for role in ["Phone A", "Phone B", "Relay"] {
        let (tx, input) = bounded_pair()?;
        let (output, rx) = bounded_pair()?;
        tx.send(b"probe!")?;
        let status = Command::new(&executable)
            .args(["probe", &endpoint.to_string()])
            .stdin(stdio(input))
            .stdout(stdio(output))
            .stderr(Stdio::null())
            .status()?;
        let mut received = [0; 7];
        let passed = status.success()
            && rx.recv(&mut received).ok() == Some(6)
            && &received[..6] == b"probe!";
        let observed = if passed {
            "denied by seccomp"
        } else {
            "isolation could not be proven"
        };
        Event {
            test: "isolation",
            tick: 0,
            action: "reject",
            from: role,
            to: "Alice",
            expected: "deny file, socket/connect, memory and descriptor syscalls",
            observed,
            status: if passed { "pass" } else { "fail" },
        }
        .emit();
        check(passed, "seccomp setup or kernel escape probe failed")?;
    }
    Ok(())
}
