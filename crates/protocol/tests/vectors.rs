use protocol::fixtures;
use serde_json::Value;
use snow::Builder;

fn hex(value: &Value) -> Vec<u8> {
    if value.is_null() {
        return Vec::new();
    }
    value
        .as_str()
        .unwrap()
        .as_bytes()
        .as_chunks::<2>()
        .0
        .iter()
        .map(|pair| u8::from_str_radix(std::str::from_utf8(pair).unwrap(), 16).unwrap())
        .collect()
}

#[test]
fn cacophony_kk_stateless() {
    run(include_str!("noise-kk.json"), 2);
}
#[test]
fn cacophony_xx_stateless() {
    run(include_str!("noise-xx.json"), 3);
}
fn run(json: &str, handshake_count: usize) {
    let vector: Value = serde_json::from_str(json).unwrap();
    let pattern = vector["protocol_name"].as_str().unwrap();
    let handshake = |who: &str, initiator: bool| {
        let field = |name| hex(&vector[format!("{who}_{name}")]);
        let (local, remote, ephemeral, prologue) = (
            field("static"),
            field("remote_static"),
            field("ephemeral"),
            field("prologue"),
        );
        let mut builder = Builder::with_resolver(pattern.parse().unwrap(), fixtures::resolver())
            .local_private_key(&local)
            .unwrap()
            .prologue(&prologue)
            .unwrap()
            .fixed_ephemeral_key_for_testing_only(&ephemeral);
        if !remote.is_empty() {
            builder = builder.remote_public_key(&remote).unwrap();
        }
        if initiator {
            builder.build_initiator().unwrap()
        } else {
            builder.build_responder().unwrap()
        }
    };
    let (mut a, mut b) = (handshake("init", true), handshake("resp", false));
    let messages = vector["messages"].as_array().unwrap();
    let mut encrypted = [0; 256];
    let mut decoded = [0; 256];
    for (index, message) in messages[..handshake_count].iter().enumerate() {
        let (tx, rx) = if index % 2 == 0 {
            (&mut a, &mut b)
        } else {
            (&mut b, &mut a)
        };
        let payload = hex(&message["payload"]);
        let len = tx.write_message(&payload, &mut encrypted).unwrap();
        assert_eq!(encrypted[..len], hex(&message["ciphertext"]));
        let len = rx.read_message(&encrypted[..len], &mut decoded).unwrap();
        assert_eq!(decoded[..len], payload);
    }
    assert_eq!(a.get_handshake_hash(), hex(&vector["handshake_hash"]));
    assert_eq!(b.get_handshake_hash(), a.get_handshake_hash());
    let a = a.into_stateless_transport_mode().unwrap();
    let b = b.into_stateless_transport_mode().unwrap();
    for (index, message) in messages[handshake_count..].iter().enumerate() {
        let (tx, rx) = if (index + handshake_count).is_multiple_of(2) {
            (&a, &b)
        } else {
            (&b, &a)
        };
        let nonce = (index / 2) as u64;
        let payload = hex(&message["payload"]);
        let len = tx.write_message(nonce, &payload, &mut encrypted).unwrap();
        assert_eq!(encrypted[..len], hex(&message["ciphertext"]));
        let len = rx
            .read_message(nonce, &encrypted[..len], &mut decoded)
            .unwrap();
        assert_eq!(decoded[..len], payload);
    }
}
