use protocol::PATTERN;
use serde_json::Value;
use snow::Builder;

fn hex(value: &Value) -> Vec<u8> {
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
    let vector: Value = serde_json::from_str(include_str!("noise-kk.json")).unwrap();
    assert_eq!(vector["protocol_name"], PATTERN);
    let handshake = |who: &str, initiator: bool| {
        let field = |name| hex(&vector[format!("{who}_{name}")]);
        let (local, remote, ephemeral, prologue) = (
            field("static"),
            field("remote_static"),
            field("ephemeral"),
            field("prologue"),
        );
        let builder = Builder::new(PATTERN.parse().unwrap())
            .local_private_key(&local)
            .unwrap()
            .remote_public_key(&remote)
            .unwrap()
            .prologue(&prologue)
            .unwrap()
            .fixed_ephemeral_key_for_testing_only(&ephemeral);
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
    for (message, (tx, rx)) in messages.iter().zip([(&mut a, &mut b)]) {
        let payload = hex(&message["payload"]);
        let len = tx.write_message(&payload, &mut encrypted).unwrap();
        assert_eq!(encrypted[..len], hex(&message["ciphertext"]));
        let len = rx.read_message(&encrypted[..len], &mut decoded).unwrap();
        assert_eq!(decoded[..len], payload);
    }
    let payload = hex(&messages[1]["payload"]);
    let len = b.write_message(&payload, &mut encrypted).unwrap();
    assert_eq!(encrypted[..len], hex(&messages[1]["ciphertext"]));
    let len = a.read_message(&encrypted[..len], &mut decoded).unwrap();
    assert_eq!(decoded[..len], payload);
    assert_eq!(a.get_handshake_hash(), hex(&vector["handshake_hash"]));
    assert_eq!(b.get_handshake_hash(), a.get_handshake_hash());
    let a = a.into_stateless_transport_mode().unwrap();
    let b = b.into_stateless_transport_mode().unwrap();
    for (index, message) in messages[2..].iter().enumerate() {
        let (tx, rx) = if index % 2 == 0 { (&a, &b) } else { (&b, &a) };
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
