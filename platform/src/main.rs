//! Public-fixture diagnostic only. Never flash this image into a real device.
#![no_std]
#![no_main]

extern crate alloc;
use core::{
    alloc::{GlobalAlloc, Layout},
    cell::UnsafeCell,
    fmt::{self, Write},
    mem::MaybeUninit,
    sync::atomic::{AtomicUsize, Ordering},
};
use cortex_m_rt::{ExceptionFrame, entry, exception};
use protocol::{
    Media, Received,
    fixtures::{self, Seeded},
};

const HEAP_BYTES: usize = 32 * 1024;
struct Arena {
    memory: UnsafeCell<[u8; HEAP_BYTES]>,
    used: AtomicUsize,
}
// SAFETY: this diagnostic runs one thread with interrupts disabled. Atomic
// reservation gives each allocation a distinct range; the arena never moves.
unsafe impl Sync for Arena {}
unsafe impl GlobalAlloc for Arena {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let base = self.memory.get() as usize;
        let mut old = self.used.load(Ordering::Relaxed);
        loop {
            let Some(start) = base
                .checked_add(old)
                .and_then(|n| n.checked_add(layout.align() - 1))
                .map(|n| n & !(layout.align() - 1))
            else {
                return core::ptr::null_mut();
            };
            let Some(end) = start
                .checked_sub(base)
                .and_then(|n| n.checked_add(layout.size()))
                .filter(|&n| n <= HEAP_BYTES)
            else {
                return core::ptr::null_mut();
            };
            match self
                .used
                .compare_exchange_weak(old, end, Ordering::Relaxed, Ordering::Relaxed)
            {
                Ok(_) => return start as *mut u8,
                Err(actual) => old = actual,
            }
        }
    }
    unsafe fn dealloc(&self, pointer: *mut u8, layout: Layout) {
        // SAFETY: GlobalAlloc gives us the live allocated range. Scrub it before
        // retirement; this diagnostic intentionally never reuses allocations.
        for i in 0..layout.size() {
            unsafe { pointer.add(i).write_volatile(0) }
        }
        core::sync::atomic::compiler_fence(Ordering::SeqCst);
    }
}
#[global_allocator]
static ARENA: Arena = Arena {
    memory: UnsafeCell::new([0; HEAP_BYTES]),
    used: AtomicUsize::new(0),
};
static mut ENCODER: MaybeUninit<codec::EncoderStorage> = MaybeUninit::uninit();
static mut DECODER: MaybeUninit<codec::DecoderStorage> = MaybeUninit::uninit();

struct Console;
impl Write for Console {
    fn write_str(&mut self, s: &str) -> fmt::Result {
        for &byte in s.as_bytes() {
            // SAFETY: ARM semihosting SYS_WRITEC with a live one-byte buffer.
            unsafe {
                core::arch::asm!("bkpt 0xab",inout("r0") 3usize=>_,in("r1") &byte,options(nostack));
            }
        }
        Ok(())
    }
}
fn exit(ok: bool) -> ! {
    let args = [0x20026usize, if ok { 0 } else { 1 }];
    // SAFETY: semihosting SYS_EXIT_EXTENDED; no application continues afterward.
    unsafe {
        core::arch::asm!("bkpt 0xab",inout("r0") 0x20usize=>_,in("r1") args.as_ptr(),options(nostack));
    }
    loop {
        core::hint::spin_loop()
    }
}
#[panic_handler]
fn panic(info: &core::panic::PanicInfo) -> ! {
    let _ = writeln!(Console, "PROBE FAILED: {info}");
    exit(false)
}
#[exception]
unsafe fn HardFault(_frame: &ExceptionFrame) -> ! {
    let _ = writeln!(Console, "PROBE FAILED: HardFault (including stack limit)");
    exit(false)
}

#[inline(never)]
fn policies() {
    use protocol::{
        Identity,
        contacts::{ContactBook, StorageRoot},
        enrollment::{Enrollment, MAX_ENROLLMENT_MESSAGE},
        invitation::{Admission, Invitation, Kind, TrustedClock, call_context},
    };
    struct Clock;
    impl TrustedClock for Clock {
        fn seconds(&self) -> u64 {
            100
        }
    }
    let mut entropy = Seeded::new(900);
    let a = Identity::new(&mut entropy).unwrap();
    let b = Identity::new(&mut entropy).unwrap();
    let mut x = Enrollment::new(&a, true, &mut entropy).unwrap();
    let mut y = Enrollment::new(&b, false, &mut entropy).unwrap();
    let mut wire = [0; MAX_ENROLLMENT_MESSAGE];
    let n = x.write(&mut wire).unwrap();
    y.read(&wire[..n]).unwrap();
    let n = y.write(&mut wire).unwrap();
    x.read(&wire[..n]).unwrap();
    let n = x.write(&mut wire).unwrap();
    y.read(&wire[..n]).unwrap();
    let mut x = x.finish().unwrap();
    let mut y = y.finish().unwrap();
    let fingerprint = x.fingerprint();
    assert_eq!(fingerprint, y.fingerprint());
    let xc = x.confirm_local(&fingerprint, true).unwrap();
    let yc = y.confirm_local(&fingerprint, true).unwrap();
    x.receive_confirmation(&yc).unwrap();
    y.receive_confirmation(&xc).unwrap();
    let mut ab = ContactBook::new(a.contact()[..32].try_into().unwrap());
    let mut ba = ContactBook::new(b.contact()[..32].try_into().unwrap());
    ab.install(x.complete().unwrap(), "Bob").unwrap();
    ba.install(y.complete().unwrap(), "Alice").unwrap();
    let mut ar = StorageRoot::new(&mut entropy).unwrap();
    let mut br = StorageRoot::new(&mut entropy).unwrap();
    let snapshot = ab.persist(&mut ar).unwrap();
    ab = ContactBook::restore(&snapshot, &ar, a.contact()[..32].try_into().unwrap()).unwrap();
    let ak = a.contact()[..32].try_into().unwrap();
    let bk = b.contact()[..32].try_into().unwrap();
    let (offer, _) = Invitation::issue(
        &a,
        &mut ab,
        &bk,
        [1; 16],
        &Clock,
        Kind::Offer,
        None,
        &mut entropy,
        &mut ar,
    )
    .unwrap();
    let (offered, _) = offer
        .verify(
            &b,
            &mut ba,
            &ak,
            &[1; 16],
            &Clock,
            &mut Admission::default(),
            &mut br,
        )
        .unwrap();
    let (accept, _) = Invitation::issue(
        &b,
        &mut ba,
        &ak,
        [2; 16],
        &Clock,
        Kind::Accept,
        Some(offered.call_nonce()),
        &mut entropy,
        &mut br,
    )
    .unwrap();
    let (accepted, _) = accept
        .verify(
            &a,
            &mut ab,
            &bk,
            &[2; 16],
            &Clock,
            &mut Admission::default(),
            &mut ar,
        )
        .unwrap();
    assert_eq!(
        call_context(&a, &ab, &offer, &accepted).unwrap(),
        call_context(&b, &ba, &accept, &offered).unwrap()
    );
    let mut radio = protocol::radio::RadioPort::default();
    assert!(radio.receive(&[0xff, 0], 1).is_err());
}

#[inline(never)]
fn boot_and_entropy() {
    use protocol::{
        PolicyError, PolicyResult,
        entropy::{EntropyPool, HardwareSources},
        update::{BootPolicy, FlashBanks, VersionFloor, fixture_image},
    };
    struct Flash([[u8; 2048]; 2]);
    impl FlashBanks for Flash {
        fn capacity(&self) -> usize {
            2048
        }
        fn read(&self, b: usize, o: usize, out: &mut [u8]) -> PolicyResult<()> {
            let input = self
                .0
                .get(b)
                .and_then(|v| v.get(o..o + out.len()))
                .ok_or(PolicyError::Storage)?;
            out.copy_from_slice(input);
            Ok(())
        }
        fn erase(&mut self, b: usize) -> PolicyResult<()> {
            self.0[b].fill(255);
            Ok(())
        }
        fn write(&mut self, b: usize, o: usize, input: &[u8]) -> PolicyResult<()> {
            self.0[b][o..o + input.len()].copy_from_slice(input);
            Ok(())
        }
    }
    let signer = ed25519_dalek::SigningKey::from_bytes(&[8; 32]);
    let policy = BootPolicy::new(7, signer.verifying_key().to_bytes()).unwrap();
    let mut flash = Flash([[255; 2048]; 2]);
    let mut floor = VersionFloor::default();
    let image = fixture_image(&[0x55; 768], 7, 1, &signer);
    assert!(
        policy
            .install_local_sd(&image, false, &mut flash, &mut floor)
            .is_err()
    );
    policy
        .install_local_sd(&image, true, &mut flash, &mut floor)
        .unwrap();
    assert_eq!(policy.boot(&flash, &mut floor).unwrap().version, 1);
    assert!(
        policy
            .install_local_sd(&image, true, &mut flash, &mut floor)
            .is_err()
    );
    struct Sources(u64);
    impl HardwareSources for Sources {
        fn next_protected_generation(&mut self) -> PolicyResult<u64> {
            self.0 += 1;
            Ok(self.0)
        }
        fn read_source(&mut self, index: usize, out: &mut [u8; 32]) -> PolicyResult<()> {
            if index == 2 {
                return Err(PolicyError::Entropy);
            }
            for (n, b) in out.iter_mut().enumerate() {
                *b = n as u8 ^ self.0 as u8 ^ (index as u8 * 31)
            }
            Ok(())
        }
    }
    let mut pool = EntropyPool::new(Sources(0));
    assert_ne!(
        pool.conditioned_seed().unwrap(),
        pool.conditioned_seed().unwrap()
    );
}

fn stack_used() -> usize {
    unsafe extern "C" {
        static _stack_end: u32;
        static _stack_start: u32;
    }
    // SAFETY: runtime painted the reserved stack with 0xCCCCCCCC before main.
    // Reading the unused region does not mutate the active stack.
    unsafe {
        let mut p = &raw const _stack_end;
        let top = &raw const _stack_start;
        while p < top && p.read_volatile() == 0xCCCCCCCC {
            p = p.add(1)
        }
        top as usize - p as usize
    }
}
#[entry]
fn main() -> ! {
    // SAFETY: no interrupts or concurrent users of the two codec slots exist.
    unsafe {
        core::arch::asm!("cpsid i", options(nostack));
    }
    let _ = writeln!(Console, "Quietlink Cortex-M33 diagnostic: PUBLIC TEST KEYS");
    policies();
    boot_and_entropy();
    let (mut local, mut peer) = fixtures::sessions(177).unwrap();
    fixtures::activate(&mut local, &mut peer).unwrap();
    let encoder = codec::encoder_in_place(unsafe { &mut *(&raw mut ENCODER) }).unwrap();
    let decoder = codec::decoder_in_place(unsafe { &mut *(&raw mut DECODER) }).unwrap();
    let mut device = device_core::Device::with_codecs(local, encoder, decoder);
    let mut checksum = 0i64;
    for slot in 0..32 {
        let media = device.encode(Some(&codec::synthetic(true, slot)));
        assert!(matches!(media, Media::Audio(_)));
        let outgoing = device.seal(slot, media).unwrap();
        let received = match peer.receive(&outgoing, slot..slot + 1).unwrap() {
            Received::Media(_, m) => m,
            _ => panic!("media"),
        };
        let incoming = peer.media(slot, received).unwrap(); // Peer fixture echoes the real encoded frame.
        // Exercise actual bounded link fragmentation and reassembly.
        let mut reassembly = link::Reassembly::default();
        let mut rejoined = None;
        for (part, n) in link::fragments(slot as u32, &incoming).unwrap() {
            if let Some(frame) = reassembly.push(&part[..n], slot).unwrap() {
                rejoined = Some(frame)
            }
        }
        let (wire, n) = rejoined.unwrap();
        device.ingest(&wire[..n], slot).unwrap();
        let (pcm, kind) = device.playout();
        assert_eq!(kind, device_core::Playout::Audio);
        checksum += pcm.iter().map(|&x| i64::from(x).abs()).sum::<i64>();
    }
    assert!(checksum > 100000);
    let stack = stack_used();
    let heap = ARENA.used.load(Ordering::Relaxed);
    let _ = writeln!(
        Console,
        "{{\"frames\":32,\"pcm_checksum\":{checksum},\"heap_cumulative_bytes\":{heap},\"stack_high_water_bytes\":{stack},\"encoder_bytes\":{},\"decoder_bytes\":{},\"contact_book_bytes\":{},\"pipeline\":\"pass\",\"policy_paths\":\"pass\"}}",
        core::mem::size_of::<codec::EncoderStorage>(),
        core::mem::size_of::<codec::DecoderStorage>(),
        core::mem::size_of::<protocol::contacts::ContactBook>()
    );
    exit(true)
}
