mod reference;
mod sandbox;
mod simulation;
mod wall;

use serde::Serialize;
use std::io::{self, Write};
use std::path::Path;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
const PEERS: [&str; 5] = ["Alice", "Phone A", "Relay", "Phone B", "Bob"];

#[derive(Serialize)]
struct Event<'a> {
    test: &'a str,
    tick: u64,
    action: &'a str,
    from: &'a str,
    to: &'a str,
    expected: &'a str,
    observed: &'a str,
    status: &'a str,
}

impl Event<'_> {
    fn emit(&self) {
        println!(
            "{}",
            serde_json::to_string(self).expect("static event strings")
        );
        io::stdout().flush().expect("event output");
    }
    fn emit_live(&self) {
        // Monitoring only: this path is never called by timing benchmarks.
        let line = format!(
            "{}\n",
            serde_json::to_string(self).expect("static event strings")
        );
        io::stderr()
            .lock()
            .write_all(line.as_bytes())
            .expect("live event output");
    }
}

fn check(condition: bool, reason: &str) -> Result<()> {
    if condition {
        Ok(())
    } else {
        Err(io::Error::other(reason).into())
    }
}

fn required(args: &[String], index: usize) -> Result<&str> {
    Ok(args.get(index).ok_or("missing argument")?)
}

fn run(args: &[String]) -> Result<()> {
    match required(args, 1)? {
        "virtual" => simulation::run(),
        "isolation" => sandbox::test(),
        "wall" => wall::run(Path::new(required(args, 2)?), required(args, 3)?),
        "endpoint" => wall::endpoint(
            Path::new(required(args, 2)?),
            required(args, 3)? == "alice",
            required(args, 4)?,
        ),
        "forward" => sandbox::forward(required(args, 2)?, required(args, 3)?.parse()?),
        "probe" => sandbox::probe(required(args, 2)?.parse()?),
        "contention" => wall::contention(required(args, 2)?.parse()?, required(args, 3)?.parse()?),
        "interop" => {
            reference::interop(Path::new(required(args, 2)?), Path::new(required(args, 3)?))
        }
        "vectors" => reference::vectors(
            Path::new(required(args, 2)?),
            Path::new(required(args, 3)?),
            Path::new(required(args, 4)?),
        ),
        _ => Err("unknown internal command".into()),
    }
}

fn main() {
    if let Err(error) = run(&std::env::args().collect::<Vec<_>>()) {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
