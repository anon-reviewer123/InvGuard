pragma solidity ^0.4.25;

interface IVictim {
    function isSaleFinished() external view returns (bool);
}

contract TimestampExploit {
    IVictim public victim;

    event ExploitResult(bool result, uint256 manipulatedTimestamp);

    constructor(address _victim) public {
        victim = IVictim(_victim);
    }

    // This function simulates mining a block with a manipulated timestamp.
    function simulateAttack() public {
        // Normally, we can't set block.timestamp directly in mainnet,
        // but in testing or with miner collusion we can manipulate timestamp.

        // Let's just read isSaleFinished() and emit result
        bool saleOver = victim.isSaleFinished();

        emit ExploitResult(saleOver, block.timestamp);

        // In a real attack, an adversary miner would:
        // 1. Mine a block at t = 1546300790
        // 2. Manipulate block.timestamp to 1546300801
        // 3. saleOver == true, even though real time < Jan 1, 2019
    }
}

