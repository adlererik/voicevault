#![forbid(unsafe_code)]

pub const FIRST_MEDIA: u64 = 2;
pub const WINDOW: u64 = 64;

#[derive(Default, Debug, Clone, Copy, PartialEq, Eq)]
pub struct Replay {
    head: Option<u64>,
    seen: u64,
}

impl Replay {
    pub fn eligible(&self, sequence: u64) -> bool {
        if sequence == u64::MAX {
            return false;
        }
        match self.head {
            Some(head) if sequence <= head => {
                let distance = head - sequence;
                distance < WINDOW && self.seen & (1 << distance) == 0
            }
            _ => true,
        }
    }

    /// Commit only an authenticated and admissible sequence.
    pub fn commit(&mut self, sequence: u64) -> bool {
        if !self.eligible(sequence) {
            return false;
        }
        match self.head {
            Some(head) if sequence <= head => self.seen |= 1 << (head - sequence),
            Some(head) if sequence - head < WINDOW => {
                self.seen = (self.seen << (sequence - head)) | 1;
                self.head = Some(sequence);
            }
            _ => {
                self.seen = 1;
                self.head = Some(sequence);
            }
        }
        true
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Control {
    Confirm,
    Ready,
}

#[derive(Default)]
pub struct CallState {
    consent: bool,
    sent_confirm: bool,
    peer_confirm: bool,
    sent_ready: bool,
    peer_ready: bool,
}

impl CallState {
    pub fn consent(&mut self) {
        self.consent = true;
    }

    pub fn can_send(&self, control: Control) -> bool {
        match control {
            Control::Confirm => self.consent && !self.sent_confirm,
            Control::Ready => self.sent_confirm && self.peer_confirm && !self.sent_ready,
        }
    }

    pub fn sent(&mut self, control: Control) -> bool {
        if !self.can_send(control) {
            return false;
        }
        match control {
            Control::Confirm => self.sent_confirm = true,
            Control::Ready => self.sent_ready = true,
        }
        true
    }

    pub fn receive(&mut self, control: Control) -> bool {
        match control {
            Control::Confirm if !self.peer_confirm => self.peer_confirm = true,
            Control::Ready if self.sent_confirm && self.peer_confirm && !self.peer_ready => {
                self.peer_ready = true;
            }
            _ => return false,
        }
        true
    }

    pub fn active(&self) -> bool {
        self.sent_ready && self.peer_ready
    }
}

#[cfg(kani)]
mod proofs {
    use super::*;

    #[kani::proof]
    fn replay_rejects_duplicate_and_preserves_preflight() {
        let mut replay = Replay::default();
        let a: u64 = kani::any();
        let b: u64 = kani::any();
        kani::assume(a != u64::MAX);
        assert!(replay.commit(a));
        let before = replay;
        let eligible = replay.eligible(b);
        assert_eq!(replay, before);
        assert_eq!(replay.commit(b), eligible);
        assert!(!replay.eligible(a));
        assert!(!replay.eligible(b));
        if !eligible {
            assert_eq!(replay, before);
        }
    }

    #[kani::proof]
    #[kani::unwind(8)]
    fn active_requires_local_consent_and_both_confirmations() {
        let mut state = CallState::default();
        for _ in 0..7 {
            match kani::any::<u8>() {
                0 => state.consent(),
                1 => {
                    state.sent(Control::Confirm);
                }
                2 => {
                    state.sent(Control::Ready);
                }
                3 => {
                    state.receive(Control::Confirm);
                }
                4 => {
                    state.receive(Control::Ready);
                }
                _ => state = CallState::default(),
            }
            if state.active() {
                assert!(state.consent && state.sent_confirm && state.peer_confirm);
                assert!(state.sent_ready && state.peer_ready);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn boundaries() {
        let mut replay = Replay::default();
        assert!(replay.commit(100));
        assert!(replay.commit(37));
        assert!(!replay.commit(36));
        assert!(!replay.commit(37));
        assert!(replay.commit(164));
        assert!(!replay.commit(100));
        assert!(!replay.commit(u64::MAX));
    }
}
